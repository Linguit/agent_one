from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import Table, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.diagnostic_contracts import DIAGNOSTIC_KIND, STATUS_MAP, DiagnosticInput
from super_ai.job_api import BackgroundJob
from super_ai.job_runtime import JobContext
from super_ai.memory.sqlite.diagnostic_schema import (
    checkpoints,
    evidence,
    links,
    reports,
    steps,
    tasks,
)
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.memory.sqlite.jobs import JobRepository, append_persisted_event, job_utc_now
from super_ai.memory.sqlite.tool_audits import audits
from super_ai.project_config import JsonObject, JsonValue
from super_ai.tenant import OwnerScope


class Diagnostics:
    def __init__(self, jobs_repository: JobRepository) -> None:
        self.jobs = jobs_repository
        self.factory = jobs_repository.factory

    async def create(self, scope: OwnerScope, body: DiagnosticInput) -> JsonObject:
        task_id = str(uuid4())
        async with self.factory.begin() as db:
            await db.execute(
                tasks.insert().values(
                    id=task_id,
                    owner_user_id=scope.owner_user_id,
                    safe_input=body.model_dump(mode="json"),
                    created_at=job_utc_now(),
                )
            )
            await self.jobs.enqueue(
                owner_user_id=scope.owner_user_id,
                kind=DIAGNOSTIC_KIND,
                resource_type="diagnostic_task",
                resource_id=task_id,
                payload={},
                timeout_seconds=300,
                max_attempts=3,
                transaction=db,
            )
        result = await self.detail(scope, task_id)
        assert result is not None
        return result

    async def latest_job(self, scope: OwnerScope, task_id: str) -> RowMapping | None:
        async with self.factory() as db:
            return (
                (
                    await db.execute(
                        select(jobs)
                        .where(
                            jobs.c.owner_user_id == scope.owner_user_id,
                            jobs.c.resource_type == "diagnostic_task",
                            jobs.c.resource_id == task_id,
                        )
                        .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )

    async def detail(self, scope: OwnerScope, task_id: str) -> JsonObject | None:
        async with self.factory() as db:
            row = (
                (
                    await db.execute(
                        select(tasks).where(
                            tasks.c.owner_user_id == scope.owner_user_id,
                            tasks.c.id == task_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        job = await self.latest_job(scope, task_id)
        assert job is not None
        report_rows = await self.rows(scope, task_id, reports)
        return {
            "id": task_id,
            "status": STATUS_MAP.get(str(job["status"]), str(job["status"])),
            "input": cast(JsonObject, row["safe_input"]),
            "createdAt": cast(datetime, row["created_at"]).isoformat(),
            "backgroundJob": cast(JsonObject, BackgroundJob.from_row(job).model_dump(mode="json")),
            "report": cast(JsonValue, report_rows[-1]) if report_rows else None,
        }

    async def list(self, scope: OwnerScope) -> list[JsonValue]:
        async with self.factory() as db:
            ids = list(
                await db.scalars(
                    select(tasks.c.id)
                    .where(
                        tasks.c.owner_user_id == scope.owner_user_id,
                    )
                    .order_by(tasks.c.created_at.desc(), tasks.c.id)
                )
            )
        return [item for id in ids if (item := await self.detail(scope, str(id))) is not None]

    async def rows(self, scope: OwnerScope, task_id: str, table: Table) -> list[JsonObject]:
        async with self.factory() as db:
            rows = (
                await db.execute(
                    select(table)
                    .where(
                        table.c.owner_user_id == scope.owner_user_id,
                        table.c.task_id == task_id,
                    )
                    .order_by(table.c.created_at, table.c.id)
                )
            ).mappings()
            return [
                cast(
                    JsonObject,
                    {
                        key: value.isoformat() if isinstance(value, datetime) else value
                        for key, value in row.items()
                    },
                )
                for row in rows
            ]
    #hain() 方法返回的是：当前用户某个诊断任务的完整过程记录，把分散在多张表中的数据汇总成一个字典
    async def chain(self, scope: OwnerScope, task_id: str) -> JsonObject:
        result: JsonObject = {
            name: cast(JsonValue, await self.rows(scope, task_id, table))
            for name, table in (
                ("steps", steps),
                ("evidence", evidence),
                ("reports", reports),
                ("links", links),
                ("checkpoints", checkpoints),
            )
        }
        async with self.factory() as db:
            calls = (
                await db.execute(
                    select(audits)
                    .where(
                        audits.c.owner_user_id == scope.owner_user_id,
                        audits.c.diagnostic_task_id == task_id,
                    )
                    .order_by(audits.c.started_at, audits.c.id)
                )
            ).mappings()
            result["toolCalls"] = cast(
                JsonValue,
                [
                    {
                        key: value.isoformat() if isinstance(value, datetime) else value
                        for key, value in call.items()
                    }
                    for call in calls
                ],
            )
        return result

    async def load(self, context: JobContext) -> JsonObject | None:
        rows = await self.rows(context.scope, str(context.job["resource_id"]), checkpoints)
        return cast(JsonObject, rows[-1]["state"]) if rows else None

    @asynccontextmanager
    async def fenced(self, context: JobContext) -> AsyncGenerator[AsyncSession]:
        async with self.factory.begin() as db:
            # UPDATE obtains the SQLite writer lock before checking/writing any child records.
            row = await db.scalar(
                update(jobs)
                .where(
                    jobs.c.id == context.id,
                    jobs.c.owner_user_id == context.scope.owner_user_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == context.job["lease_owner"],
                    jobs.c.lease_expires_at > job_utc_now(),
                    jobs.c.cancel_requested_at.is_(None),
                )
                .values(updated_at=job_utc_now())
                .returning(jobs.c.id)
            )
            if row is None:
                raise asyncio.CancelledError
            yield db

    async def insert(
        self,
        db: AsyncSession,
        context: JobContext,
        table: Table,
        values: dict[str, object],
    ) -> str:
        id = str(uuid4())
        await db.execute(
            table.insert().values(
                id=id,
                owner_user_id=context.scope.owner_user_id,
                task_id=str(context.job["resource_id"]),
                created_at=job_utc_now(),
                **values,
            )
        )
        return id

    async def event(
        self,
        db: AsyncSession,
        context: JobContext,
        kind: str,
        data: JsonObject,
    ) -> None:
        await append_persisted_event(db, context.id, kind, job_utc_now(), data)

    async def save(self, context: JobContext, state: JsonObject, next_node: str) -> None:
        async with self.fenced(context) as db:
            await self.insert(
                db,
                context,
                checkpoints,
                {
                    "job_id": context.id,
                    "state": {**state, "next": next_node},
                    "next_node": next_node,
                    "plan_version": state.get("version", 0),
                },
            )
