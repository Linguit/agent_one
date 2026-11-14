import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import async_sessionmaker

from super_ai.job_runtime import JobContext, JobHandlers, JobWorker
from super_ai.main import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite import jobs
from super_ai.memory.sqlite.jobs import JobRepository

OWNER = "owner"


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    return url


@pytest.fixture
async def repository(database_url: str) -> AsyncGenerator[JobRepository]:
    engine = create_engine(DatabaseSettings(url=database_url))
    try:
        yield JobRepository(async_sessionmaker(engine))
    finally:
        await engine.dispose()


async def enqueue(
    repo: JobRepository, *, owner: str = OWNER, attempts: int = 2, timeout: int = 10
) -> str:
    job = await repo.enqueue(
        owner_user_id=owner,
        kind="test",
        resource_type="doc",
        resource_id="resource",
        payload={"secret": "sentinel"},
        max_attempts=attempts,
        timeout_seconds=timeout,
    )
    return str(job["id"])


async def read(repo: JobRepository, job_id: str, owner: str = OWNER) -> RowMapping:
    row = await repo.get(job_id, owner_user_id=owner)
    assert row is not None
    return row


async def wait_status(
    repo: JobRepository, job_id: str, status: str, owner: str = OWNER
) -> RowMapping:
    for _ in range(400):
        row = await read(repo, job_id, owner)
        if row["status"] == status:
            return row
        await asyncio.sleep(0.015)
    pytest.fail(f"未到达状态 {status}")


async def test_claim_heartbeat_expiry_and_restart(
    repository: JobRepository, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 13)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)
    job_id = await enqueue(repository)
    claims = await asyncio.gather(*(repository.claim(("test",), 30) for _ in range(8)))
    (first,) = [row for row in claims if row is not None]
    now += timedelta(seconds=20)
    renewed = await repository.heartbeat(first, 30)
    assert renewed is not None and renewed["lease_expires_at"] == now + timedelta(seconds=30)
    now += timedelta(seconds=11)
    await repository.recover_expired()
    assert (await read(repository, job_id))["status"] == "running"

    now += timedelta(seconds=20)
    engine = create_engine(DatabaseSettings(url=database_url))
    try:
        restarted = JobRepository(async_sessionmaker(engine))
        await restarted.recover_expired()
        assert await restarted.claim(("test",), 30) is None
        assert (await read(restarted, job_id))["available_at"] == now + timedelta(seconds=1)
        now += timedelta(seconds=1)
        second = await restarted.claim(("test",), 30)
        assert second is not None and second["attempt"] == 2
        assert await repository.heartbeat(first, 30) is None
        assert not await repository.append_event(first, "stale", {}, owner_user_id=OWNER)
        assert not await restarted.append_event(second, "foreign", {}, owner_user_id="other")
        await repository.finish(first, "succeeded")
        assert (await read(restarted, job_id))["status"] == "running"
        await restarted.finish(second, "handler_error")
        assert (await read(restarted, job_id))["status"] == "failed"
        assert [
            event["kind"] for event in await restarted.list_events(job_id, owner_user_id=OWNER)
        ] == ["queued", "running", "retry_scheduled", "running", "failed"]
    finally:
        await engine.dispose()


async def test_backoff_limit_and_manual_retry(
    repository: JobRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 13)
    monkeypatch.setattr(jobs, "_utc_now", lambda: now)
    job_id = await enqueue(repository, attempts=8)
    for delay in (1, 2, 4, 8, 16, 30, 30):
        job = await repository.claim(("test",), 30)
        assert job is not None
        await repository.finish(job, "handler_error")
        assert (await read(repository, job_id))["available_at"] == now + timedelta(seconds=delay)
        now += timedelta(seconds=delay)
    job = await repository.claim(("test",), 30)
    assert job is not None and job["attempt"] == 8
    await repository.finish(job, "handler_error")
    assert (await read(repository, job_id))["status"] == "failed"
    assert await repository.retry(job_id, owner_user_id="other") is None
    retry = await repository.retry(job_id, owner_user_id=OWNER)
    assert retry is not None
    assert retry["id"] != job_id and retry["retry_of_job_id"] == job_id
    assert retry["status"] == "queued" and retry["attempt"] == 0
    assert retry["payload"] == {"secret": "sentinel"}


async def test_worker_timeout_and_cancellation(repository: JobRepository) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def handler(_: JobContext) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    handlers = JobHandlers()
    handlers.register("test", handler)
    queued = await enqueue(repository)
    assert await repository.cancel(queued, owner_user_id="other") is None
    await repository.cancel(queued, owner_user_id=OWNER)
    assert (await read(repository, queued))["status"] == "cancelled"

    timed = await enqueue(repository, attempts=1, timeout=1)
    async with JobWorker(repository, handlers, poll_seconds=0.025, lease_seconds=0.4):
        failed = await wait_status(repository, timed, "failed")
        assert failed["error_message"] == "任务执行超时。"
        assert stopped.is_set()
        stopped.clear()
        started.clear()
        running = await enqueue(repository)
        await asyncio.wait_for(started.wait(), timeout=5)
        await repository.cancel(running, owner_user_id=OWNER)
        await wait_status(repository, running, "cancelled")
        assert stopped.is_set()


async def test_worker_error_is_redacted(
    repository: JobRepository, caplog: pytest.LogCaptureFixture
) -> None:
    async def handler(context: JobContext) -> None:
        raise RuntimeError(str(context.payload))

    handlers = JobHandlers()
    handlers.register("test", handler)
    job_id = await enqueue(repository, attempts=1)
    async with JobWorker(repository, handlers, poll_seconds=0.025):
        row = await wait_status(repository, job_id, "failed")
    assert row["error_message"] == "任务执行失败。"
    assert "sentinel" not in caplog.text
    assert "sentinel" not in str(await repository.list_events(job_id, owner_user_id=OWNER))


async def test_lifespan_http_isolation_and_replay(database_url: str) -> None:
    proceed = asyncio.Event()
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def handler(context: JobContext) -> None:
        await context.emit("progress", {"step": 1})
        started.set()
        try:
            await proceed.wait()
        finally:
            cleaned.set()

    handlers = JobHandlers()
    handlers.register("test", handler)
    app = create_app(config={"database": {"url": database_url}}, job_handlers=handlers)

    async with app.router.lifespan_context(app):
        repo: JobRepository = app.state.job_repository
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            async def register(name: str) -> tuple[str, dict[str, str]]:
                credentials = {"email": f"{name}@example.test", "password": "test-password"}
                user = await client.post("/auth/register", json=credentials)
                login = await client.post("/auth/login", json=credentials)
                return user.json()["data"]["id"], {
                    "Authorization": f"Bearer {login.json()['data']['token']}"
                }

            owner, headers = await register("owner")
            other, other_headers = await register("other")
            job_id = await enqueue(repo, owner=owner)
            await asyncio.wait_for(started.wait(), timeout=5)
            url = f"/background-jobs/{job_id}"
            assert (await client.get(url)).status_code == 401
            response = await client.get(url, headers=headers)
            assert response.status_code == 200 and "sentinel" not in response.text
            assert (await client.get(url, headers=other_headers)).status_code == 404
            for action in ("cancel", "retry"):
                assert (
                    await client.post(f"{url}:{action}", headers=other_headers)
                ).status_code == 404
            assert (await client.get("/background-jobs", headers=other_headers)).json()[
                "data"
            ] == []
            assert await repo.list_events(job_id, owner_user_id=other) == []
            initial = await repo.list_events(job_id, owner_user_id=owner)
            assert [event["sequence"] for event in initial] == [1, 2, 3]
            second_id = await enqueue(repo, owner=owner)
            cancelled = await client.post(f"/background-jobs/{second_id}:cancel", headers=headers)
            assert cancelled.status_code == 200
            await wait_status(repo, second_id, "cancelled", owner)
            retry = await client.post(f"/background-jobs/{second_id}:retry", headers=headers)
            assert retry.status_code == 200
            assert retry.json()["data"]["retryOfJobId"] == second_id
            await wait_status(repo, retry.json()["data"]["id"], "running", owner)

        proceed.set()
        await wait_status(repo, job_id, "succeeded", owner)
        await wait_status(repo, retry.json()["data"]["id"], "succeeded", owner)
        replay = await repo.list_events(job_id, owner_user_id=owner, after_sequence=3)
        assert [(event["sequence"], event["kind"]) for event in replay] == [(4, "succeeded")]
        assert len(await repo.list_events(job_id, owner_user_id=owner)) == 4

        paths = app.openapi()["paths"]
        for path, method in (
            ("/background-jobs", "get"),
            ("/background-jobs/{id}", "get"),
            ("/background-jobs/{id}:cancel", "post"),
            ("/background-jobs/{id}:retry", "post"),
        ):
            assert "application/json" in paths[path][method]["responses"]["200"]["content"]

        proceed.clear()
        started.clear()
        cleaned.clear()
        await enqueue(repo, owner=owner)
        await asyncio.wait_for(started.wait(), timeout=5)
    assert cleaned.is_set()
