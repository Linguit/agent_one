import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from super_ai.diagnosis_case_persistor import DiagnosisCasePersistor
from super_ai.diagnostic_case_source import report_section
from super_ai.diagnostic_contracts import DIAGNOSTIC_KIND, DiagnosticInput
from super_ai.document_api import default_knowledge_base_id
from super_ai.document_indexing import DocumentIndexer
from super_ai.job_runtime import JobContext, JobHandlers, JobWorker
from super_ai.knowledge_retrieval import KnowledgeRetrieval, KnowledgeRetrievalInput
from super_ai.llm_provider import LlmProvider, RerankHit
from super_ai.main import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite.diagnostic_cases import DiagnosticCaseRepository, cases
from super_ai.memory.sqlite.diagnostic_schema import checkpoints, evidence, reports
from super_ai.memory.sqlite.diagnostics import Diagnostics
from super_ai.memory.sqlite.documents import DocumentRepository, documents
from super_ai.memory.sqlite.index_tasks import INDEX_TASK_KIND
from super_ai.memory.sqlite.index_tasks import tasks as index_tasks
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.project_config import JsonObject, JsonValue
from super_ai.tenant import OwnerScope
from super_ai.vector_store import MilvusVectorStore, VectorChunk

SCOPE = OwnerScope("owner", "owner")
REPORT = """# 告警分析报告
## 📋 活跃告警清单
测试告警 ConnectionPool
## 🔍 告警根因分析1
### 根因结论
连接池证据不足，无法确认根因（仅测试生命周期，不支撑产品结论）。
## 🛠️ 处理方案执行1
### 已执行步骤
仅保存测试边界结果，未执行修复。
### 建议
人工核验连接池，勿声称已处理。password=case-sentinel
## 📊 结论
### 整体评估
ConnectionPool 仍需核验。
### 关键发现
没有确认根因。
"""


@dataclass
class Environment:
    jobs: JobRepository
    documents: DocumentRepository
    persistor: DiagnosisCasePersistor


@pytest.fixture
async def env(tmp_path: Path) -> AsyncGenerator[Environment]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'cases.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    engine = create_engine(DatabaseSettings(url=url))
    repo = JobRepository(async_sessionmaker(engine))

    def delete_vectors(scope: OwnerScope, kb: str, document: str) -> None:
        pass

    docs = DocumentRepository(repo.factory, delete_vectors)
    persistor = DiagnosisCasePersistor(repo, docs, ("case-sentinel",))
    repo.success_hooks[DIAGNOSTIC_KIND] = persistor.on_succeeded
    try:
        yield Environment(repo, docs, persistor)
    finally:
        await engine.dispose()


async def seed(
    repo: JobRepository,
    *,
    scope: OwnerScope = SCOPE,
    status: str = "succeeded",
    report: bool = True,
    final: bool = True,
    with_evidence: bool = True,
) -> tuple[str, JobContext]:
    diagnostic = await Diagnostics(repo).create(scope, DiagnosticInput(query="ConnectionPool"))
    async with repo.factory.begin() as db:
        await db.execute(
            update(jobs).where(jobs.c.resource_id == diagnostic["id"]).values(max_attempts=1)
        )
    row = await repo.claim((DIAGNOSTIC_KIND,), 30)
    assert row is not None
    context = JobContext(repo, row)
    await write_report(context, report=report, final=final, with_evidence=with_evidence)
    if status == "cancelled":
        await repo.cancel(context.id, owner_user_id=scope.owner_user_id)
    if status != "running":
        await repo.finish(
            row, "succeeded" if status in ("succeeded", "cancelled") else "handler_error"
        )
    return str(diagnostic["id"]), context


async def write_report(
    context: JobContext,
    *,
    report: bool = True,
    final: bool = True,
    with_evidence: bool = True,
) -> None:
    repo = Diagnostics(context.repository)
    async with repo.fenced(context) as db:
        if with_evidence:
            await repo.insert(
                db,
                context,
                evidence,
                {
                    "kind": "alert",
                    "source": "test-provider-boundary",
                    "step_id": None,
                    "content": {"alertname": "ConnectionPool", "service": "checkout"},
                },
            )
        if report:
            await repo.insert(
                db,
                context,
                reports,
                {
                    "job_id": context.id,
                    "content": REPORT,
                    "mode": "fallback",
                },
            )
        if final:
            await repo.insert(
                db,
                context,
                checkpoints,
                {
                    "job_id": context.id,
                    "next_node": "end",
                    "plan_version": 1,
                    "state": {"next": "end", "version": 1},
                },
            )


async def counts(repo: JobRepository) -> tuple[int, int, int, int]:
    async with repo.factory() as db:
        return tuple(
            [
                int(await db.scalar(select(func.count()).select_from(table)) or 0)
                for table in (cases, documents, index_tasks, jobs)
            ]
        )  # type: ignore[return-value]


async def test_success_hook_creates_structured_case_document_and_index(env: Environment) -> None:
    task_id, context = await seed(env.jobs)
    rows = await DiagnosticCaseRepository(env.jobs.factory).list_cases(SCOPE)
    assert len(rows) == 1
    case = rows[0]
    assert (
        case.task_id == task_id
        and case.alert_name == "ConnectionPool"
        and case.service == "checkout"
    )
    assert "无法确认根因" in case.root_cause and "未处理" not in case.remediation
    assert "勿声称已处理" in case.remediation
    assert "case-sentinel" not in case.model_dump_json()
    document = await env.documents.get(SCOPE, default_knowledge_base_id(SCOPE), case.document_id)
    assert document is not None and document["index_status"] == "pending"
    assert "# 诊断故障案例" in document["body"] and "## 原始诊断报告" in document["body"]
    assert "case-sentinel" not in document["body"]
    metadata = document["metadata"]
    assert metadata["knowledgeType"] == "diagnostic-case"
    assert (
        metadata["sourceDiagnosticTaskId"] == task_id
        and metadata["sourceReportId"] == case.report_id
    )
    assert metadata["sourceEvidenceIds"] == case.evidence_ids and case.evidence_ids
    assert await counts(env.jobs) == (1, 1, 1, 2)
    await env.jobs.finish(context.job, "succeeded")
    assert await counts(env.jobs) == (1, 1, 1, 2)


@pytest.mark.parametrize(
    "status,report,final",
    [
        ("failed", True, True),
        ("cancelled", True, True),
        ("running", True, True),
        ("succeeded", False, True),
        ("succeeded", True, False),
    ],
)
async def test_ineligible_diagnoses_never_create_cases(
    env: Environment,
    status: str,
    report: bool,
    final: bool,
) -> None:
    task_id, _ = await seed(env.jobs, status=status, report=report, final=final)
    assert await env.persistor.persist(SCOPE, task_id) is None
    assert (await counts(env.jobs))[:3] == (0, 0, 0)


async def test_empty_evidence_snapshot_and_concurrent_idempotency(env: Environment) -> None:
    hook = env.jobs.success_hooks.pop(DIAGNOSTIC_KIND)
    task_id, _ = await seed(env.jobs, with_evidence=False)
    env.jobs.success_hooks[DIAGNOSTIC_KIND] = hook
    assert (await counts(env.jobs))[:3] == (0, 0, 0)
    values = await asyncio.gather(*(env.persistor.persist(SCOPE, task_id) for _ in range(8)))
    assert all(value is not None and value.evidence_ids == [] for value in values)
    assert len({value.id for value in values if value}) == 1
    assert await counts(env.jobs) == (1, 1, 1, 2)
    # A later evidence insert must not rewrite the case's original evidence snapshot.
    async with env.jobs.factory.begin() as db:
        await db.execute(
            evidence.insert().values(
                id=str(uuid4()),
                owner_user_id=SCOPE.owner_user_id,
                task_id=task_id,
                created_at=datetime.now(),
                step_id=None,
                kind="log",
                source="test-boundary",
                content={"message": "later test record"},
            )
        )
    again = await env.persistor.persist(SCOPE, task_id)
    assert again and again.evidence_ids == []
    other = OwnerScope("other", "other")
    assert await env.persistor.persist(other, task_id) is None
    repo = DiagnosticCaseRepository(env.jobs.factory)
    assert await repo.list_cases(other) == [] and await repo.get(other, again.id) is None


async def test_case_failure_rolls_back_success_and_recovers(
    env: Environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id, context = await seed(env.jobs, status="running")
    original = env.persistor.indexing.create

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("index enqueue unavailable")

    monkeypatch.setattr(env.persistor.indexing, "create", fail)
    with pytest.raises(RuntimeError):
        await env.jobs.finish(context.job, "succeeded")
    job = await env.jobs.get(context.id, owner_user_id="owner")
    assert job is not None and job["status"] == "running"
    assert (await counts(env.jobs))[:3] == (0, 0, 0)
    monkeypatch.setattr(env.persistor.indexing, "create", original)
    await env.jobs.finish(context.job, "succeeded")
    assert await env.persistor.persist(SCOPE, task_id) is not None
    assert await counts(env.jobs) == (1, 1, 1, 2)


async def test_worker_completion_automatically_persists_case(env: Environment) -> None:
    task = await Diagnostics(env.jobs).create(SCOPE, DiagnosticInput(query="ConnectionPool"))
    handlers = JobHandlers()
    handlers.register(DIAGNOSTIC_KIND, write_report)
    async with JobWorker(env.jobs, handlers, poll_seconds=0.02):
        for _ in range(150):
            if (await counts(env.jobs))[0] == 1:
                break
            await asyncio.sleep(0.02)
    case = (await DiagnosticCaseRepository(env.jobs.factory).list_cases(SCOPE))[0]
    assert case.task_id == task["id"]


async def authenticate(client: httpx.AsyncClient, name: str) -> tuple[OwnerScope, dict[str, str]]:
    credentials = {"email": f"{name}@test.local", "password": "test-password"}
    await client.post("/auth/register", json=credentials)
    login = (await client.post("/auth/login", json=credentials)).json()["data"]
    owner = login["user"]["id"]
    return OwnerScope(owner, owner), {"Authorization": f"Bearer {login['token']}"}


async def test_legacy_save_and_case_api_are_distinct_and_owner_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def idle_slot(self: JobWorker) -> None:
        await asyncio.Event().wait()

    # Endpoint checks seed jobs; the separate worker test covers actual scheduling.
    monkeypatch.setattr(JobWorker, "_slot", idle_slot)
    url = f"sqlite+aiosqlite:///{(tmp_path / 'api.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    handlers = JobHandlers()

    async def blocked(context: JobContext) -> None:
        await asyncio.Event().wait()

    handlers.register(INDEX_TASK_KIND, blocked)
    handlers.register(DIAGNOSTIC_KIND, blocked)
    app = create_app(config={"database": {"url": url}}, job_handlers=handlers)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            scope, headers = await authenticate(c, "case-owner")
            _, other = await authenticate(c, "case-other")
            repo = cast(JobRepository, app.state.job_repository)
            # Seed a historical successful diagnosis without the new automatic hook.
            hook = repo.success_hooks.pop(DIAGNOSTIC_KIND)
            task_id, _ = await seed(repo, scope=scope)
            repo.success_hooks[DIAGNOSTIC_KIND] = hook
            manual = await c.post(
                f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=headers
            )
            assert manual.status_code == 200
            assert (await counts(repo))[:3] == (0, 1, 1)
            duplicate = await c.post(
                f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=headers
            )
            assert (
                duplicate.status_code == 409
                and duplicate.json()["error"]["code"] == "BUSINESS_CONFLICT"
            )
            hook = repo.success_hooks.pop(DIAGNOSTIC_KIND)
            another_task, _ = await seed(repo, scope=scope)
            repo.success_hooks[DIAGNOSTIC_KIND] = hook
            same_content = await c.post(
                f"/aiops/diagnostics/{another_task}:save-to-knowledge",
                headers=headers,
            )
            assert same_content.status_code == 409
            assert (await counts(repo))[:3] == (0, 1, 1)
            # Automatic source-task idempotency is independent from manual content deduplication.
            case = await cast(DiagnosisCasePersistor, app.state.diagnosis_case_persistor).persist(
                scope, task_id
            )
            assert case is not None and (await counts(repo))[:3] == (1, 2, 2)
            assert (await c.get("/aiops/diagnostic-cases", headers=headers)).json()["data"][0][
                "id"
            ] == case.id
            assert (
                await c.get(f"/aiops/diagnostic-cases/{case.id}", headers=headers)
            ).status_code == 200
            assert (await c.get("/aiops/diagnostic-cases", headers=other)).json()["data"] == []
            assert (
                await c.get(f"/aiops/diagnostic-cases/{case.id}", headers=other)
            ).status_code == 404
            assert (
                await c.post(f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=other)
            ).status_code == 404
            assert (await c.get("/aiops/diagnostic-cases")).status_code == 401
            for status in ("failed", "cancelled"):
                task_id, _ = await seed(repo, scope=scope, status=status)
                assert (
                    await c.post(f"/aiops/diagnostics/{task_id}:save-to-knowledge", headers=headers)
                ).status_code == 409


class CaseVectors:
    def __init__(self) -> None:
        self.records: list[VectorChunk] = []

    def initialize(self) -> None:
        pass

    def close(self) -> None:
        pass

    def delete_document(self, scope: OwnerScope, kb: str, document: str) -> None:
        self.records = [row for row in self.records if row.document_id != document]

    def insert(self, scope: OwnerScope, chunks: list[VectorChunk]) -> None:
        self.records.extend(chunks)

    def search(self, *args: Any, **kwargs: Any) -> list[dict[str, JsonValue]]:
        return [
            {
                "distance": 1.0,
                "entity": {
                    "chunkId": row.chunk_id,
                    "documentId": row.document_id,
                    "knowledgeBaseId": row.knowledge_base_id,
                    "tenantId": "owner",
                    "ownerUserId": "owner",
                },
            }
            for row in self.records
        ]


class CaseProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankHit]:
        return [
            RerankHit(index=i, relevance_score=0.8) for i in range(min(top_n or 5, len(documents)))
        ]


async def test_case_uses_normal_indexer_and_is_retrieved_with_provenance(env: Environment) -> None:
    task_id, _ = await seed(env.jobs)
    case = await env.persistor.persist(SCOPE, task_id)
    assert case is not None
    vectors = CaseVectors()

    @asynccontextmanager
    async def provider() -> AsyncGenerator[LlmProvider]:
        yield cast(LlmProvider, CaseProvider())

    retrieval = KnowledgeRetrieval(
        env.jobs.factory, provider, lambda: cast(MilvusVectorStore, vectors)
    )
    params = KnowledgeRetrievalInput(query="ConnectionPool")
    assert await retrieval.retrieve(SCOPE, params) == {"results": []}
    job = await env.jobs.claim((INDEX_TASK_KIND,), 30)
    assert job is not None
    await DocumentIndexer(env.documents, provider, lambda: vectors).run(JobContext(env.jobs, job))
    assert vectors.records and all(
        row.metadata["knowledgeType"] == "diagnostic-case" for row in vectors.records
    )
    result = await retrieval.retrieve(SCOPE, params)
    hits = cast(list[JsonObject], result["results"])
    assert hits and all(hit["documentId"] == case.document_id for hit in hits)
    metadata = cast(JsonObject, hits[0]["metadata"])
    assert (
        metadata["sourceDiagnosticTaskId"] == task_id
        and metadata["sourceEvidenceIds"] == case.evidence_ids
    )
    assert await retrieval.retrieve(OwnerScope("other", "other"), params) == {"results": []}
    assert await env.documents.delete(SCOPE, default_knowledge_base_id(SCOPE), case.document_id)
    assert await retrieval.retrieve(SCOPE, params) == {"results": []}


def test_report_extraction_preserves_uncertainty() -> None:
    assert "无法确认根因" in report_section(REPORT, "根因结论")
    assert report_section("# unrelated", "根因结论") == ""


def test_migration_roundtrip(tmp_path: Path) -> None:
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from alembic import command

    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0011_aiops_diagnostics")
    engine = create_engine(url)
    try:
        with engine.begin() as db:
            db.execute(
                text("""
                INSERT INTO knowledge_documents
                (id, owner_user_id, knowledge_base_id, filename, size, mime_type, sha256,
                 uploaded_at, index_status, chunking, body)
                VALUES ('old', 'owner', 'kb', 'old.md', 1, 'text/markdown', 'old',
                        CURRENT_TIMESTAMP, 'pending', '{"strategy":"paragraph"}', 'historical')
            """)
            )
    finally:
        engine.dispose()
    command.upgrade(config, "head")
    command.downgrade(config, "0011_aiops_diagnostics")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT metadata FROM knowledge_documents WHERE id='old'")) == "{}"
            )
        assert "aiops_diagnostic_cases" in inspector.get_table_names()
        assert any(
            column["name"] == "metadata" for column in inspector.get_columns("knowledge_documents")
        )
        assert any(
            unique["column_names"] == ["task_id"]
            for unique in inspector.get_unique_constraints("aiops_diagnostic_cases")
        )
    finally:
        engine.dispose()
