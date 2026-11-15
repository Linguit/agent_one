from collections.abc import Callable
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    and_,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from super_ai.document_contracts import ChunkingConfig
from super_ai.memory.base import Base
from super_ai.tenant import OwnerScope

documents = Table(
    "knowledge_documents",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_user_id", String(36), nullable=False),
    Column("knowledge_base_id", String(36), nullable=False),
    Column("filename", String, nullable=False),
    Column("size", Integer, nullable=False),
    Column("mime_type", String, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("uploaded_at", DateTime, nullable=False),
    Column("index_status", String, nullable=False),
    Column("chunking", JSON, nullable=False),
    Column("body", Text, nullable=False),
    Column("deleted_at", DateTime),
)
Index(
    "uq_knowledge_documents_active_hash",
    documents.c.owner_user_id,
    documents.c.knowledge_base_id,
    documents.c.sha256,
    unique=True,
    sqlite_where=documents.c.deleted_at.is_(None),
)

DeleteVectors = Callable[[OwnerScope, str, str], object]


class DuplicateDocument(Exception):
    pass


class DocumentRepository:
    def __init__(
        self, factory: async_sessionmaker[AsyncSession], delete_vectors: DeleteVectors
    ) -> None:
        self._factory = factory
        self._delete_vectors = delete_vectors

    @staticmethod
    def _active(scope: OwnerScope, kb: str):
        return and_(
            documents.c.owner_user_id == scope.owner_user_id,
            documents.c.knowledge_base_id == kb,
            documents.c.deleted_at.is_(None),
        )

    async def list(self, scope: OwnerScope, kb: str) -> list[RowMapping]:
        columns = [column for column in documents.c if column.name != "body"]
        statement = (
            select(*columns)
            .where(self._active(scope, kb))
            .order_by(documents.c.uploaded_at.desc(), documents.c.id)
        )
        async with self._factory() as session:
            return list((await session.execute(statement)).mappings())

    async def get(self, scope: OwnerScope, kb: str, document: str) -> RowMapping | None:
        statement = select(documents).where(self._active(scope, kb), documents.c.id == document)
        async with self._factory() as session:
            return (await session.execute(statement)).mappings().one_or_none()

    async def add(
        self,
        scope: OwnerScope,
        kb: str,
        *,
        filename: str,
        size: int,
        mime_type: str,
        sha256: str,
        chunking: ChunkingConfig,
        body: str,
        overwrite: bool,
    ) -> RowMapping:
        async with self._factory.begin() as session:
            await session.execute(text("BEGIN IMMEDIATE"))
            old_id = (
                await session.execute(
                    select(documents.c.id).where(
                        self._active(scope, kb), documents.c.sha256 == sha256
                    )
                )
            ).scalar_one_or_none()
            if old_id is not None:
                if not overwrite:
                    raise DuplicateDocument
                await self._soft_delete(session, scope, kb, cast(str, old_id))
            statement = (
                insert(documents)
                .values(
                    id=str(uuid4()),
                    owner_user_id=scope.owner_user_id,
                    knowledge_base_id=kb,
                    filename=filename,
                    size=size,
                    mime_type=mime_type,
                    sha256=sha256,
                    uploaded_at=datetime.now(timezone.utc),
                    index_status="pending",
                    chunking=chunking.model_dump(mode="json"),
                    body=body,
                )
                .returning(*[column for column in documents.c if column.name != "body"])
            )
            return (await session.execute(statement)).mappings().one()

    async def delete(self, scope: OwnerScope, kb: str, document: str) -> bool:
        async with self._factory.begin() as session:
            await session.execute(text("BEGIN IMMEDIATE"))
            return await self._soft_delete(session, scope, kb, document)

    async def _soft_delete(
        self, session: AsyncSession, scope: OwnerScope, kb: str, document: str
    ) -> bool:
        statement = (
            update(documents)
            .where(self._active(scope, kb), documents.c.id == document)
            .values(deleted_at=datetime.now(timezone.utc))
            .returning(documents.c.id)
        )
        deleted = (await session.execute(statement)).scalar_one_or_none()
        if deleted is None:
            return False
        await run_in_threadpool(self._delete_vectors, scope, kb, document)
        return True
