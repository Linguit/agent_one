from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from sqlalchemy import case, func, literal, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from super_ai.memory.base import utc_now
from super_ai.memory.engine import session_scope
from super_ai.memory.sqlite.job_schema import events, jobs
from super_ai.project_config import JsonObject
from super_ai.tenant import require_owner_user_id

JobOutcome = Literal["succeeded", "handler_error", "timeout", "lease_expired"]
ERRORS: dict[JobOutcome, str] = {
    "handler_error": "任务执行失败。",
    "timeout": "任务执行超时。",
    "lease_expired": "任务租约已过期。",
}


def _utc_now() -> datetime:
    return utc_now().replace(tzinfo=None)


def _scope(owner_user_id: str) -> ColumnElement[bool]:
    return jobs.c.owner_user_id == require_owner_user_id(owner_user_id)


def _running(job: RowMapping) -> tuple[ColumnElement[bool], ...]:
    return (
        jobs.c.id == job["id"],
        jobs.c.status == "running",
        jobs.c.lease_owner == job["lease_owner"],
    )


async def _event(
    session: AsyncSession,
    job_id: str,
    kind: str,
    now: datetime,
    data: JsonObject,
) -> None:
    sequence = (
        select(func.coalesce(func.max(events.c.sequence), 0) + 1)
        .where(events.c.job_id == job_id)
        .scalar_subquery()
    )
    await session.execute(
        events.insert().values(
            job_id=job_id, sequence=sequence, kind=kind, created_at=now, data=data
        )
    )


class JobRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def enqueue(
        self,
        *,
        owner_user_id: str,
        kind: str,
        resource_type: str,
        resource_id: str,
        payload: JsonObject,
        max_attempts: int = 3,
        timeout_seconds: int = 300,
    ) -> RowMapping:
        require_owner_user_id(owner_user_id)
        if not kind or max_attempts < 1 or timeout_seconds < 1:
            raise ValueError("任务类型、最大尝试次数或超时时间无效")
        now, job_id = _utc_now(), str(uuid4())
        async with session_scope(self.factory) as session:
            row = await session.execute(
                jobs.insert()
                .values(
                    id=job_id,
                    owner_user_id=owner_user_id,
                    kind=kind,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    payload=payload,
                    status="queued",
                    attempt=0,
                    max_attempts=max_attempts,
                    timeout_seconds=timeout_seconds,
                    available_at=now,
                    created_at=now,
                    updated_at=now,
                )
                .returning(*jobs.c)
            )
            await _event(session, job_id, "queued", now, {})
            return row.mappings().one()

    async def list_jobs(self, *, owner_user_id: str) -> list[RowMapping]:
        async with self.factory() as session:
            result = await session.execute(
                select(jobs)
                .where(_scope(owner_user_id))
                .order_by(jobs.c.created_at.desc(), jobs.c.id)
            )
            return list(result.mappings())

    async def get(self, job_id: str, *, owner_user_id: str) -> RowMapping | None:
        async with self.factory() as session:
            result = await session.execute(
                select(jobs).where(_scope(owner_user_id), jobs.c.id == job_id)
            )
            return result.mappings().one_or_none()

    async def list_events(
        self, job_id: str, *, owner_user_id: str, after_sequence: int = 0
    ) -> list[RowMapping]:
        async with self.factory() as session:
            result = await session.execute(
                select(events)
                .join(jobs, events.c.job_id == jobs.c.id)
                .where(
                    _scope(owner_user_id), jobs.c.id == job_id, events.c.sequence > after_sequence
                )
                .order_by(events.c.sequence)
            )
            return list(result.mappings())

    async def cancel(self, job_id: str, *, owner_user_id: str) -> RowMapping | None:
        now = _utc_now()
        queued = jobs.c.status == "queued"
        scoped = (_scope(owner_user_id), jobs.c.id == job_id)
        async with session_scope(self.factory) as session:
            result = await session.execute(
                update(jobs)
                .where(
                    *scoped,
                    jobs.c.status.in_(("queued", "running")),
                    jobs.c.cancel_requested_at.is_(None),
                )
                .values(
                    status=case((queued, "cancelled"), else_=jobs.c.status),
                    cancel_requested_at=now,
                    updated_at=now,
                    completed_at=case((queued, now), else_=jobs.c.completed_at),
                )
                .returning(*jobs.c)
            )
            row = result.mappings().one_or_none()
            if row is not None:
                kind = "cancelled" if row["status"] == "cancelled" else "cancel_requested"
                await _event(session, job_id, kind, now, {})
                return row
            return (await session.execute(select(jobs).where(*scoped))).mappings().one_or_none()

    async def retry(self, job_id: str, *, owner_user_id: str) -> RowMapping | None:
        now, new_id = _utc_now(), str(uuid4())
        async with session_scope(self.factory) as session:
            result = await session.execute(
                jobs.insert()
                .from_select(
                    [
                        "id",
                        "owner_user_id",
                        "kind",
                        "resource_type",
                        "resource_id",
                        "payload",
                        "status",
                        "attempt",
                        "max_attempts",
                        "timeout_seconds",
                        "available_at",
                        "retry_of_job_id",
                        "created_at",
                        "updated_at",
                    ],
                    select(
                        literal(new_id),
                        jobs.c.owner_user_id,
                        jobs.c.kind,
                        jobs.c.resource_type,
                        jobs.c.resource_id,
                        jobs.c.payload,
                        literal("queued"),
                        literal(0),
                        jobs.c.max_attempts,
                        jobs.c.timeout_seconds,
                        literal(now),
                        jobs.c.id,
                        literal(now),
                        literal(now),
                    ).where(
                        _scope(owner_user_id),
                        jobs.c.id == job_id,
                        jobs.c.status.in_(("failed", "cancelled")),
                    ),
                )
                .returning(*jobs.c)
            )
            row = result.mappings().one_or_none()
            if row is not None:
                await _event(session, new_id, "queued", now, {})
            return row

    async def claim(self, kinds: tuple[str, ...], lease_seconds: float) -> RowMapping | None:
        now = _utc_now()
        candidate = (
            select(jobs.c.id)
            .where(jobs.c.status == "queued", jobs.c.kind.in_(kinds), jobs.c.available_at <= now)
            .order_by(jobs.c.available_at, jobs.c.created_at, jobs.c.id)
            .limit(1)
            .scalar_subquery()
        )
        async with session_scope(self.factory) as session:
            result = await session.execute(
                update(jobs)
                .where(jobs.c.id == candidate)
                .values(
                    status="running",
                    attempt=jobs.c.attempt + 1,
                    started_at=now,
                    updated_at=now,
                    lease_owner=str(uuid4()),
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    error_message=None,
                )
                .returning(*jobs.c)
            )
            row = result.mappings().one_or_none()
            if row is not None:
                await _event(session, row["id"], "running", now, {"attempt": row["attempt"]})
            return row

    async def heartbeat(self, job: RowMapping, lease_seconds: float) -> RowMapping | None:
        now = _utc_now()
        async with session_scope(self.factory) as session:
            result = await session.execute(
                update(jobs)
                .where(*_running(job), jobs.c.lease_expires_at > now)
                .values(lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now)
                .returning(*jobs.c)
            )
            return result.mappings().one_or_none()

    async def append_event(
        self, job: RowMapping, kind: str, data: JsonObject, *, owner_user_id: str
    ) -> bool:
        now = _utc_now()
        async with session_scope(self.factory) as session:
            result = await session.execute(
                update(jobs)
                .where(
                    *_running(job),
                    _scope(owner_user_id),
                    jobs.c.lease_expires_at > now,
                    jobs.c.cancel_requested_at.is_(None),
                )
                .values(updated_at=now)
                .returning(jobs.c.id)
            )
            if result.scalar_one_or_none() is None:
                return False
            await _event(session, job["id"], kind, now, data)
            return True

    async def finish(self, job: RowMapping, outcome: JobOutcome) -> None:
        now = _utc_now()
        expired = outcome == "lease_expired"
        expiry = jobs.c.lease_expires_at <= now if expired else jobs.c.lease_expires_at > now
        retry = outcome != "succeeded" and job["attempt"] < job["max_attempts"]
        delay = min(30, 2 ** min(5, job["attempt"] - 1))
        cancelled = jobs.c.cancel_requested_at.is_not(None)
        status = "succeeded" if outcome == "succeeded" else ("queued" if retry else "failed")
        async with session_scope(self.factory) as session:
            result = await session.execute(
                update(jobs)
                .where(*_running(job), expiry)
                .values(
                    status=case((cancelled, "cancelled"), else_=status),
                    error_message=case((cancelled, None), else_=ERRORS.get(outcome)),
                    available_at=case(
                        (~cancelled, now + timedelta(seconds=delay)), else_=jobs.c.available_at
                    )
                    if retry
                    else jobs.c.available_at,
                    updated_at=now,
                    lease_owner=None,
                    lease_expires_at=None,
                    completed_at=case((cancelled, now), else_=None if retry else now),
                )
                .returning(*jobs.c)
            )
            row = result.mappings().one_or_none()
            if row is not None:
                kind = "retry_scheduled" if row["status"] == "queued" else row["status"]
                await _event(session, row["id"], kind, now, {"attempt": row["attempt"]})

    async def recover_expired(self) -> None:
        async with self.factory() as session:
            expired = list(
                (
                    await session.execute(
                        select(jobs)
                        .where(jobs.c.status == "running", jobs.c.lease_expires_at <= _utc_now())
                        .order_by(jobs.c.lease_expires_at)
                        .limit(32)
                    )
                ).mappings()
            )
        for job in expired:
            await self.finish(job, "lease_expired")
