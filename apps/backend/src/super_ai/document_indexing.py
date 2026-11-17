import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from math import isfinite
from typing import Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import TypeAdapter
from sqlalchemy import select, text
from starlette.concurrency import run_in_threadpool

from super_ai.document_chunking import chunk_document_text
from super_ai.document_contracts import ChunkingConfig
from super_ai.job_runtime import JobContext
from super_ai.memory.sqlite.documents import DocumentRepository, documents
from super_ai.memory.sqlite.index_tasks import tasks
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope
from super_ai.vector_store import VECTOR_DIMENSION, VectorChunk

_chunking = TypeAdapter[ChunkingConfig](ChunkingConfig)


def stable_chunk_id(document: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"super-ai:chunk:{document}:{index}"))


class DocumentEmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class IndexVectorStore(Protocol):
    def initialize(self) -> None: ...
    def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str, /
    ) -> object: ...
    def insert(self, scope: OwnerScope, chunks: list[VectorChunk]) -> object: ...
    def close(self) -> None: ...


class DocumentIndexer:
    def __init__(
        self,
        documents_repository: DocumentRepository,
        provider: Callable[[], AbstractAsyncContextManager[DocumentEmbeddingProvider]],
        vectors: Callable[[], IndexVectorStore],
    ) -> None:
        self.documents = documents_repository
        self.provider = provider
        self.vectors = vectors

    async def run(self, context: JobContext) -> None:
        scope = context.scope
        task_id = str(context.job["resource_id"])
        async with context.repository.factory() as session:
            task = (
                (
                    await session.execute(
                        select(tasks).where(
                            tasks.c.id == task_id,
                            tasks.c.owner_user_id == scope.owner_user_id,
                        )
                    )
                )
                .mappings()
                .one()
            )
        kb, document = str(task["knowledge_base_id"]), str(task["document_id"])
        row = await self.documents.get(scope, kb, document)
        if row is None:
            raise ValueError("文档不可索引")

        config = _chunking.validate_python(row["chunking"])
        chunks = await run_in_threadpool(
            lambda: list(chunk_document_text(cast(str, row["body"]), config))
        )
        if not chunks:
            raise ValueError("文档没有可索引分块")
        async with self.provider() as provider:
            vectors = await provider.embed([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks) or any(
            len(vector) != VECTOR_DIMENSION or not all(map(isfinite, vector)) for vector in vectors
        ):
            raise ValueError("嵌入响应无效")

        created_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        config_metadata = cast(JsonObject, config.model_dump(mode="json"))
        records = [
            VectorChunk(
                chunk_id=stable_chunk_id(document, chunk.index),
                document_id=document,
                knowledge_base_id=kb,
                content=chunk.text,
                source=str(row["filename"]),
                created_at=created_at,
                metadata={
                    "chunking": config_metadata,
                    "index": chunk.index,
                    "start": chunk.start,
                    "end": chunk.end,
                },
                vector=vector,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        async with context.repository.factory.begin() as session:
            await session.execute(text("BEGIN IMMEDIATE"))
            lease = await session.scalar(
                select(jobs.c.id).where(
                    jobs.c.id == context.id,
                    jobs.c.owner_user_id == scope.owner_user_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == context.job["lease_owner"],
                    jobs.c.lease_expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
                    jobs.c.cancel_requested_at.is_(None),
                )
            )
            if lease is None:
                raise asyncio.CancelledError
            current = await session.scalar(
                select(documents.c.id).where(
                    documents.c.id == document,
                    documents.c.owner_user_id == scope.owner_user_id,
                    documents.c.knowledge_base_id == kb,
                    documents.c.deleted_at.is_(None),
                )
            )
            if current is None:
                raise ValueError("文档不可索引")
            # SDK 同步操作结束前持有锁，避免取消释放锁后仍写入已删除文档。
            mutation = asyncio.create_task(
                run_in_threadpool(self._replace, scope, kb, document, records)
            )
            try:
                await asyncio.shield(mutation)
            except asyncio.CancelledError:
                await asyncio.gather(mutation, return_exceptions=True)
                raise
            await context.repository.finish(context.job, "succeeded", transaction=session)

    def _replace(
        self, scope: OwnerScope, kb: str, document: str, records: list[VectorChunk]
    ) -> None:
        store = self.vectors()
        try:
            store.initialize()
            store.delete_document(scope, kb, document)
            store.insert(scope, records)
        finally:
            store.close()
