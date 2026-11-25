import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from super_ai.alert_inputs import ActiveAlerts
from super_ai.diagnostic_contracts import (
    DIAGNOSTIC_KIND,
    DiagnosticInput,
    Finding,
    Plan,
    Replan,
    ReportDraft,
)
from super_ai.diagnostic_report import build_report
from super_ai.diagnostic_runtime import (
    DiagnosticFailure,
    DiagnosticRunner,
    evidence_items,
    validate_plan,
)
from super_ai.job_runtime import JobContext, JobHandlers, JobWorker
from super_ai.main import create_app
from super_ai.mcp_provider import McpProvider
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite.diagnostic_schema import evidence, steps
from super_ai.memory.sqlite.diagnostics import Diagnostics
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.memory.sqlite.tool_audits import ToolAuditRepository, audits
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope

SCOPE = OwnerScope("owner", "owner")


@asynccontextmanager
async def no_model() -> AsyncGenerator[BaseChatModel]:
    raise RuntimeError("测试不得连接真实模型")
    yield cast(BaseChatModel, None)


@pytest.fixture
async def repo(tmp_path: Path) -> AsyncGenerator[Diagnostics]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'diagnostic.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    engine = create_engine(DatabaseSettings(url=url))
    try:
        yield Diagnostics(JobRepository(async_sessionmaker(engine)))
    finally:
        await engine.dispose()


def tool(name: str, function: Any) -> BaseTool:
    class Arguments(BaseModel):
        query: str

    return StructuredTool.from_function(
        coroutine=function, name=name, description="测试 provider 边界", args_schema=Arguments
    )


def runner_for(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
    *,
    sop: bool = False,
    fail: bool = False,
    missing: bool = False,
    many: bool = False,
) -> tuple[DiagnosticRunner, list[str]]:
    calls: list[str] = []

    async def knowledge(query: str) -> JsonObject:
        calls.append("knowledge")
        return {
            "results": [{"source": "test SOP", "excerpt": "仅测试 provider 边界"}] if sop else []
        }

    async def logs(query: str) -> JsonObject:
        calls.append("logs")
        if fail:
            raise RuntimeError("password=DO_NOT_LEAK")
        return {"logs": [], "notice": "测试边界空返回，不能用于产品根因结论"}

    async def discover(scope: OwnerScope, *, allow_fallback: bool = True) -> list[BaseTool]:
        assert scope == SCOPE and allow_fallback is False
        assert calls[0] == "knowledge"  # SOP first, discovery second.
        calls.append("discover")
        return [] if missing else [tool("SearchLog", logs)]

    async def alerts() -> ActiveAlerts:
        return ActiveAlerts(items=[])

    async def ask(schema: type[BaseModel], prompt: str, data: JsonObject) -> BaseModel:
        del prompt, data
        if schema is Plan:
            return Plan.model_validate(
                {
                    "steps": [
                        {
                            "tool": "SearchLog",
                            "arguments": {"query": "service:test"},
                            "purpose": "查询日志",
                        },
                        *(
                            [
                                {
                                    "tool": "knowledge_retrieval",
                                    "arguments": {"query": "SOP"},
                                    "purpose": "补充知识",
                                }
                            ]
                            * 5
                            if many
                            else []
                        ),
                    ]
                }
            )
        if schema is Replan:
            return Replan(action="continue", message="基于已有证据继续")
        raise RuntimeError("报告模型失败，必须诚实 fallback")

    mcp = cast(McpProvider, object())

    # Explicit boundary replacement: no test log can substantiate a production conclusion.
    class TestMcp:
        tools = staticmethod(discover)

    mcp = cast(McpProvider, TestMcp())
    runner = DiagnosticRunner(
        repo,
        no_model,
        lambda _: tool("knowledge_retrieval", knowledge),
        mcp,
        alerts,
        ToolAuditRepository(repo.factory),
        ("DO_NOT_LEAK",),
    )
    monkeypatch.setattr(runner, "ask", ask)
    return runner, calls


async def claimed(repo: Diagnostics) -> JobContext:
    row = await repo.jobs.claim((DIAGNOSTIC_KIND,), 30)
    assert row is not None
    return JobContext(repo.jobs, row)


@pytest.mark.parametrize("sop,fail", [(False, False), (True, False), (True, True)])
async def test_graph_real_constraints_normalization_fallback(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
    sop: bool,
    fail: bool,
) -> None:
    runner, calls = runner_for(repo, monkeypatch, sop=sop, fail=fail)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    await runner.run(context)
    await repo.jobs.finish(context.job, "succeeded")
    chain = await repo.chain(SCOPE, str(task["id"]))
    assert calls[:2] == ["knowledge", "discover"] and calls.count("logs") == 1
    encoded = json.dumps(chain, ensure_ascii=False)
    assert "DO_NOT_LEAK" not in encoded and "无法确认根因" in encoded
    report = cast(list[JsonObject], chain["reports"])[0]
    assert report["mode"] == "fallback"
    for heading in (
        "# 告警分析报告",
        "## 📋 活跃告警清单",
        "## 🔍 告警根因分析1",
        "## 🛠️ 处理方案执行1",
        "## 📊 结论",
    ):
        assert heading in str(report["content"])
    evidence = cast(list[JsonObject], chain["evidence"])
    assert any(item["kind"] == "knowledge" for item in evidence) == sop
    assert not any(item["kind"] == "log" for item in evidence) if fail else True
    ids = {str(item["id"]) for item in evidence}
    assert all(str(link["evidence_id"]) in ids for link in cast(list[JsonObject], chain["links"]))
    assert chain["checkpoints"]
    assert (await repo.detail(SCOPE, str(task["id"]))) is not None
    other = OwnerScope("other", "other")
    assert await repo.detail(other, str(task["id"])) is None
    assert all(not value for value in (await repo.chain(other, str(task["id"]))).values())
    async with repo.factory() as db:
        rows = (await db.execute(select(audits))).mappings().all()
        assert len(rows) == 2 and all(row["diagnostic_task_id"] == task["id"] for row in rows)


async def test_missing_searchlog_explicit_failure(
    repo: Diagnostics, monkeypatch: pytest.MonkeyPatch
):
    runner, calls = runner_for(repo, monkeypatch, missing=True)
    await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    with pytest.raises(DiagnosticFailure, match="SYSTEM_UNAVAILABLE"):
        await runner.run(context)
    assert "logs" not in calls
    events = await repo.jobs.list_events(context.id, owner_user_id="owner")
    assert events[-1]["data"]["code"] == "SYSTEM_UNAVAILABLE"


async def test_plan_rejects_unknown_duplicate_and_bad_schema() -> None:
    async def logs(query: str) -> str:
        return query

    registry = {"SearchLog": tool("SearchLog", logs)}
    for names in (["SearchLog", "unknown"], ["SearchLog", "SearchLog"], ["unknown"]):
        with pytest.raises(DiagnosticFailure):
            validate_plan(
                Plan.model_validate(
                    {
                        "steps": [
                            {"tool": name, "arguments": {"query": "x"}, "purpose": "测试"}
                            for name in names
                        ]
                    }
                ),
                registry,
            )


async def test_replan_bound_and_restart_does_not_repeat_log(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, calls = runner_for(repo, monkeypatch, many=True)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    await runner.run(context)
    saved = await repo.load(context)
    assert saved is not None and cast(int, saved["replans"]) <= 3
    assert calls.count("logs") == 1
    await runner.run(context)
    assert calls.count("logs") == 1
    # Resume after process death between starting a tool and saving its result.
    async with repo.fenced(context) as db:
        await db.execute(
            steps.update().where(steps.c.task_id == task["id"]).values(status="started")
        )
    saved.update(next="executor", replans=0)
    await repo.save(context, saved, "executor")
    await runner.run(context)
    assert calls.count("logs") == 1
    assert "OUTCOME_UNKNOWN_AFTER_RESTART" in json.dumps(await repo.chain(SCOPE, str(task["id"])))


async def test_cancel_fences_report_and_retry(repo: Diagnostics, monkeypatch: pytest.MonkeyPatch):
    runner, _ = runner_for(repo, monkeypatch)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    await repo.jobs.cancel(context.id, owner_user_id="owner")
    with pytest.raises(asyncio.CancelledError):
        await runner.run(context)
    await repo.jobs.finish(context.job, "timeout")
    assert (await repo.detail(SCOPE, str(task["id"]))) is not None
    retry = await repo.jobs.retry(context.id, owner_user_id="owner")
    assert retry is not None
    detail = await repo.detail(SCOPE, str(task["id"]))
    assert detail is not None and detail["status"] == "accepted"


async def test_worker_survives_client_disconnect_and_stream_replay(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'http.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    handlers = JobHandlers()
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(context: JobContext) -> None:
        entered.set()
        await release.wait()
        await context.emit(
            "task.status",
            {
                "status": "running",
                "task": {
                    "message": "测试持久事件",
                    "progress": 0.5,
                },
            },
        )

    handlers.register(DIAGNOSTIC_KIND, handler)
    app = create_app(config={"database": {"url": url}}, job_handlers=handlers)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            credentials = {"email": "diag@test.local", "password": "test-password"}
            await c.post("/auth/register", json=credentials)
            login = (await c.post("/auth/login", json=credentials)).json()["data"]
            headers = {"Authorization": f"Bearer {login['token']}"}
            created = await c.post(
                "/aiops/diagnostics", headers=headers, json={"query": "token=SECRET"}
            )
            assert created.status_code == 200
            data = created.json()["data"]
            assert "SECRET" not in created.text and data["backgroundJob"]["status"] == "queued"
            id = data["id"]
        await asyncio.wait_for(entered.wait(), 5)
        release.set()
        repo = cast(Diagnostics, app.state.diagnostics)
        detail: JsonObject | None = None
        for _ in range(100):
            detail = await repo.detail(OwnerScope(login["user"]["id"], login["user"]["id"]), id)
            if detail and detail["status"] == "succeeded":
                break
            await asyncio.sleep(0.03)
        assert detail and detail["status"] == "succeeded"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            stream = await c.post(f"/aiops/diagnostics/{id}:stream", headers=headers, json={})
            assert "event: complete" in stream.text and "event: task.status" in stream.text
            frames = [
                json.loads(line[6:])
                for line in stream.text.splitlines()
                if line.startswith("data: ")
            ]
            sequences = [event["sequence"] for event in frames]
            assert sequences == sorted(set(sequences))
            restored = await c.post(
                f"/aiops/diagnostics/{id}:stream",
                headers=headers,
                json={"afterSequence": sequences[-2]},
            )
            assert "event: complete" in restored.text and "测试持久事件" not in restored.text
            assert (await c.get(f"/aiops/diagnostics/{id}")).status_code == 401
            other_credentials = {"email": "other@test.local", "password": "test-password"}
            await c.post("/auth/register", json=other_credentials)
            other_login = (await c.post("/auth/login", json=other_credentials)).json()["data"]
            other_headers = {"Authorization": f"Bearer {other_login['token']}"}
            for suffix in ("", "/evidence-chain"):
                assert (
                    await c.get(f"/aiops/diagnostics/{id}{suffix}", headers=other_headers)
                ).status_code == 404
            assert (
                await c.post(f"/aiops/diagnostics/{id}:stream", headers=other_headers, json={})
            ).status_code == 404
            assert (await c.get("/aiops/diagnostics", headers=other_headers)).json()["data"] == []


async def test_worker_lease_restart_resumes_completed_evidence(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, calls = runner_for(repo, monkeypatch)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    paused = asyncio.Event()
    original_save = repo.save

    async def save(context: JobContext, state: JsonObject, next_node: str) -> None:
        if next_node == "replanner":
            paused.set()
            await asyncio.Event().wait()  # Simulate process death after tool commit.
        await original_save(context, state, next_node)

    monkeypatch.setattr(repo, "save", save)
    handlers = JobHandlers()
    handlers.register(DIAGNOSTIC_KIND, runner.run)
    async with JobWorker(repo.jobs, handlers, concurrency=1, lease_seconds=0.3, poll_seconds=0.02):
        await asyncio.wait_for(paused.wait(), 5)
    monkeypatch.setattr(repo, "save", original_save)
    async with JobWorker(repo.jobs, handlers, concurrency=1, lease_seconds=0.3, poll_seconds=0.02):
        detail: JsonObject | None = None
        for _ in range(200):
            detail = await repo.detail(SCOPE, str(task["id"]))
            if detail and detail["status"] == "succeeded":
                break
            await asyncio.sleep(0.02)
        assert detail and detail["status"] == "succeeded"
    assert calls.count("logs") == 1


async def test_worker_timeout_persists_failed_status(repo: Diagnostics) -> None:
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    async with repo.factory.begin() as db:
        await db.execute(
            update(jobs)
            .where(jobs.c.resource_id == task["id"])
            .values(
                timeout_seconds=1,
                max_attempts=1,
            )
        )

    async def blocked(context: JobContext) -> None:
        await asyncio.Event().wait()

    handlers = JobHandlers()
    handlers.register(DIAGNOSTIC_KIND, blocked)
    async with JobWorker(repo.jobs, handlers, poll_seconds=0.02):
        detail: JsonObject | None = None
        for _ in range(100):
            detail = await repo.detail(SCOPE, str(task["id"]))
            if detail and detail["status"] == "failed":
                break
            await asyncio.sleep(0.02)
        assert detail and detail["status"] == "failed"
    job = await repo.latest_job(SCOPE, str(task["id"]))
    assert job is not None
    events = await repo.jobs.list_events(str(job["id"]), owner_user_id="owner")
    assert events[-1]["kind"] == "failed"
    assert events[-2]["kind"] == "task.status" and events[-2]["data"]["status"] == "failed"


def test_migration_roundtrip_and_composite_links(tmp_path: Path) -> None:
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from alembic import command

    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{(tmp_path / 'roundtrip.db').as_posix()}"
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    command.downgrade(config, "0010_mcp_connections")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        constraints = inspector.get_foreign_keys("report_evidence_links")
        assert {fk["referred_table"] for fk in constraints} == {
            "diagnostic_tasks",
            "diagnostic_reports",
            "diagnostic_evidence",
        }
    finally:
        engine.dispose()


@pytest.mark.parametrize("valid", [True, False])
async def test_report_provenance_rejects_invented_evidence(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
    valid: bool,
) -> None:
    runner, _ = runner_for(repo, monkeypatch)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    async with repo.fenced(context) as db:
        evidence_id = await repo.insert(
            db,
            context,
            evidence,
            {
                "kind": "log",
                "source": "test-provider-boundary",
                "step_id": None,
                "content": {"message": "测试记录，仅验证引用，不支撑产品根因结论"},
            },
        )

    async def ask(schema: type[BaseModel], prompt: str, data: JsonObject) -> BaseModel:
        return ReportDraft(
            findings=[
                Finding(
                    text="仅确认引用记录存在，根因未确认。",
                    evidenceIds=[evidence_id if valid else "invented"],
                )
            ],
            recommendation="需真实环境人工核验。",
        )

    monkeypatch.setattr(runner, "ask", ask)
    await build_report(runner, context, {"version": 1, "plan": {"steps": []}})
    chain = await repo.chain(SCOPE, str(task["id"]))
    report = cast(list[JsonObject], chain["reports"])[0]
    assert report["mode"] == ("model" if valid else "fallback")
    links = cast(list[JsonObject], chain["links"])
    assert links and all(row["evidence_id"] == evidence_id for row in links)
    assert "invented" not in json.dumps(chain)


async def test_multiple_alerts_keep_distinct_report_sections(
    repo: Diagnostics,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, _ = runner_for(repo, monkeypatch)
    task = await repo.create(SCOPE, DiagnosticInput(query="test"))
    context = await claimed(repo)
    async with repo.fenced(context) as db:
        for name in ("测试告警A", "测试告警B"):
            await repo.insert(
                db,
                context,
                evidence,
                {
                    "kind": "alert",
                    "source": "test-boundary",
                    "step_id": None,
                    "content": {"alertname": name, "annotations": {"summary": name + "症状"}},
                },
            )
    await build_report(runner, context, {"version": 1})
    chain = await repo.chain(SCOPE, str(task["id"]))
    content = str(cast(list[JsonObject], chain["reports"])[0]["content"])
    assert "## 🔍 告警根因分析2" in content and "## 🛠️ 处理方案执行2" in content
    assert "测试告警A症状" in content and "测试告警B症状" in content
    assert len(cast(list[JsonObject], chain["links"])) >= 2


def test_mcp_log_blocks_are_split_and_error_is_not_evidence() -> None:
    records = evidence_items(
        [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "logs": [
                            {"message": "test boundary 1"},
                            {"message": "test boundary 2"},
                        ]
                    }
                ),
            }
        ],
        "log",
    )
    assert len(records) == 2
    assert evidence_items({"logs": []}, "log") == []
    with pytest.raises(DiagnosticFailure):
        evidence_items([{"type": "text", "text": '{"isError":true}'}], "log")
