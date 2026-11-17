import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from test_knowledge_documents import register_user

from super_ai.document_indexing import DocumentIndexer
from super_ai.job_runtime import JobContext, JobHandler, JobHandlers
from super_ai.llm_provider import EMBEDDING_DIMENSIONS, LlmProvider, create_llm_provider
from super_ai.main import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine, session_factory
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite import jobs as job_clock
from super_ai.memory.sqlite.documents import DocumentRepository
from super_ai.memory.sqlite.index_tasks import INDEX_TASK_KIND
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope
from super_ai.vector_store import VectorChunk


def test_index_task_openapi() -> None:
    schema = create_app(config={}).openapi()
    collection = "/knowledge-bases/{kb}/documents/{document}/index-tasks"
    paths = schema["paths"]
    assert {"401", "403", "404", "409"} <= paths[collection]["post"]["responses"].keys()
    assert paths[collection + "/{task}"]["get"]["security"]
    assert paths[collection + "/{task}:retry"]["post"]["responses"]["200"]
    assert paths[collection + "/{task}:cancel"]["post"]["responses"]["200"]
    models = schema["components"]["schemas"]
    statuses = ["pending", "running", "succeeded", "failed", "cancelled"]
    assert models["DocumentIndexTask"]["properties"]["status"]["enum"] == statuses
    assert models["KnowledgeDocument"]["properties"]["indexStatus"]["enum"] == statuses


class Vectors:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.records: list[VectorChunk] = []
        self.scope: OwnerScope | None = None
        self.deleted: tuple[OwnerScope, str, str] | None = None
        self.fail = False

    def initialize(self) -> None:
        self.actions.append("initialize")

    def delete_document(self, scope: OwnerScope, kb: str, document: str) -> None:
        self.actions.append("delete")
        self.deleted = (scope, kb, document)
        self.records.clear()

    def insert(self, scope: OwnerScope, chunks: list[VectorChunk]) -> None:
        self.actions.append("insert")
        if self.fail:
            raise ValueError("private-sentinel")
        self.scope = scope
        self.records = chunks

    def close(self) -> None:
        self.actions.append("close")


async def wait_task(
    client: httpx.AsyncClient, path: str, headers: dict[str, str], status: str
) -> httpx.Response:
    for _ in range(350):
        response = await client.get(path, headers=headers)
        assert response.status_code == 200
        if response.json()["data"]["status"] == status:
            return response
        await asyncio.sleep(0.035)
    pytest.fail(f"任务未进入 {status}")


async def test_indexing_pipeline(tmp_path: Path) -> None:
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite+aiosqlite:///{(tmp_path / 'index.db').as_posix()}"
    upgrade_head(url, backend)
    config = cast(
        JsonObject,
        json.loads(
            (backend.parents[1] / "config" / "project.template.json").read_text(encoding="utf-8")
        ),
    )
    llm = cast(JsonObject, config["llm"])
    llm.update({"apiKey": "fixture-key", "retries": 0})
    engine = create_engine(DatabaseSettings(url=url))
    factory = session_factory(engine)
    vectors = Vectors()
    batches: list[list[str]] = []
    block = asyncio.Event()
    block.set()
    entered = asyncio.Event()

    async def embed(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        inputs = cast(list[str], payload["input"])
        assert 0 < len(inputs) <= 10
        batches.append(inputs)
        entered.set()
        await block.wait()
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [float(value)] * EMBEDDING_DIMENSIONS}
                    for i, value in enumerate(inputs)
                ],
            },
        )

    @asynccontextmanager
    async def provider() -> AsyncGenerator[LlmProvider]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(embed)) as http:
            async with create_llm_provider(config, openai_client=http) as instance:
                yield instance

    handlers = JobHandlers()
    indexer = DocumentIndexer(
        DocumentRepository(factory, vectors.delete_document), provider, lambda: vectors
    )
    handlers.register(INDEX_TASK_KIND, indexer.run)
    app = create_app(config={"database": {"url": url}}, job_handlers=handlers)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client,
        ):
            owner_id, owner = await register_user(client, "indexer")
            _, other = await register_user(client, "other")
            bases = (await client.get("/knowledge-bases", headers=owner)).json()["data"]
            kb = str(bases[0]["id"])
            path = f"/knowledge-bases/{kb}/documents"
            sections = [str(i) for i in range(23)]
            body = "\n\n".join(sections).encode()
            uploaded = await client.post(
                path,
                headers=owner,
                files={"file": ("data.md", body, "text/markdown")},
                data={"strategy": "paragraph"},
            )
            assert uploaded.status_code == 200
            document = str(uploaded.json()["data"]["id"])
            detail = f"{path}/{document}"
            collection = f"{detail}/index-tasks"
            jobs = JobRepository(factory)
            assert await jobs.list_jobs(owner_user_id=owner_id) == []
            assert (await client.post(collection)).status_code == 401
            assert (await client.post(collection, headers=other)).status_code == 403
            created = await client.post(collection, headers=owner)
            assert created.status_code == 200
            assert created.json()["meta"]["requestId"] == created.headers["X-Request-ID"]
            first = created.json()["data"]
            assert first["status"] == "pending"
            first_url = f"{collection}/{first['id']}"
            assert (await client.post(collection, headers=owner)).status_code == 409
            done = (await wait_task(client, first_url, owner, "succeeded")).json()["data"]
            assert done["startedAt"] and done["completedAt"]
            assert (await client.get(detail, headers=owner)).json()["data"]["indexStatus"] == (
                "succeeded"
            )
            (job,) = await jobs.list_jobs(owner_user_id=owner_id)
            assert (job["resource_type"], job["resource_id"]) == (INDEX_TASK_KIND, first["id"])
            assert batches == [sections[:10], sections[10:20], sections[20:]]
            assert vectors.actions == ["initialize", "delete", "insert", "close"]
            scope = OwnerScope(owner_id, owner_id)
            assert vectors.deleted == (scope, kb, document)
            assert vectors.scope == scope
            rows = [chunk.to_row(scope) for chunk in vectors.records]
            assert len({str(row["chunkId"]) for row in rows}) == 23
            for index, row in enumerate(rows):
                assert row["content"] == sections[index]
                assert row["documentId"] == document and row["knowledgeBaseId"] == kb
                assert row["ownerUserId"] == row["tenantId"] == owner_id
                assert row["source"] == "data.md" and row["createdAt"]
                metadata = cast(JsonObject, row["metadata"])
                assert metadata["chunking"] == {"strategy": "paragraph"}
                assert metadata["index"] == index
                assert cast(list[float], row["vector"])[0] == float(index)

            vectors.fail = True
            rebuilt = (await client.post(first_url + ":retry", headers=owner)).json()["data"]
            assert rebuilt["retryOfTaskId"] == first["id"]
            failed_url = f"{collection}/{rebuilt['id']}"
            failed = await wait_task(client, failed_url, owner, "failed")
            assert failed.json()["data"]["failureReason"]
            assert "private-sentinel" not in failed.text
            assert (await client.get(detail, headers=owner)).json()["data"][
                "indexStatus"
            ] == "failed"

            vectors.fail = False
            entered.clear()
            block.clear()
            retried = (await client.post(failed_url + ":retry", headers=owner)).json()["data"]
            assert retried["retryOfTaskId"] == rebuilt["id"]
            retry_url = f"{collection}/{retried['id']}"
            await asyncio.wait_for(entered.wait(), timeout=5)
            await wait_task(client, retry_url, owner, "running")
            assert (await client.post(retry_url + ":cancel", headers=owner)).status_code == 200
            await wait_task(client, retry_url, owner, "cancelled")
            assert (await client.get(detail, headers=owner)).json()["data"]["indexStatus"] == (
                "cancelled"
            )
            assert not vectors.records
            block.set()
            recovered = (await client.post(retry_url + ":retry", headers=owner)).json()["data"]
            assert recovered["retryOfTaskId"] == retried["id"]
            await wait_task(client, f"{collection}/{recovered['id']}", owner, "succeeded")
            assert len(vectors.records) == 23
    finally:
        await engine.dispose()


async def test_index_task_recovers_after_worker_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'restart.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    started = asyncio.Event()
    successful_job_ids: list[str] = []

    async def interrupted(context: JobContext) -> None:
        started.set()
        await asyncio.Future[None]()

    async def resumed(context: JobContext) -> None:
        successful_job_ids.append(context.id)

    def app_for(handler: JobHandler) -> FastAPI:
        handlers = JobHandlers()
        handlers.register(INDEX_TASK_KIND, handler)
        return create_app(config={"database": {"url": url}}, job_handlers=handlers)

    first = app_for(interrupted)
    async with (
        first.router.lifespan_context(first),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=first),
            base_url="http://test",
        ) as client,
    ):
        _, owner = await register_user(client, "restart")
        kb = (await client.get("/knowledge-bases", headers=owner)).json()["data"][0]["id"]
        path = f"/knowledge-bases/{kb}/documents"
        response = await client.post(
            path,
            headers=owner,
            files={
                "file": ("test.md", b"restart", "text/plain"),
            },
        )
        collection = f"{path}/{response.json()['data']['id']}/index-tasks"
        created = await client.post(collection, headers=owner)
        task_url = f"{collection}/{created.json()['data']['id']}"
        await asyncio.wait_for(started.wait(), timeout=5)
        await wait_task(client, task_url, owner, "running")
        first_job = (await client.get("/background-jobs", headers=owner)).json()["data"][0]

    monkeypatch.setattr(
        job_clock,
        "_utc_now",
        lambda: datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1),
    )
    second = app_for(resumed)
    async with (
        second.router.lifespan_context(second),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second),
            base_url="http://test",
        ) as client,
    ):
        await wait_task(client, task_url, owner, "succeeded")
        assert successful_job_ids == [first_job["id"]]
        job = (await client.get("/background-jobs", headers=owner)).json()["data"][0]
        assert job["attempt"] == 2
