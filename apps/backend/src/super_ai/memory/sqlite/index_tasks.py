from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Table, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.memory.base import Base
from super_ai.memory.sqlite.documents import documents
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.tenant import OwnerScope

INDEX_TASK_KIND = "document_index_task"

tasks = Table(
    "document_index_tasks",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_user_id", String(36), nullable=False),
    Column("knowledge_base_id", String(36), nullable=False),
    Column("document_id", String(36), nullable=False),
    Column("status", String, nullable=False),
    Column("failure_reason", String),
    Column("retry_of_task_id", String(36)),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Column("started_at", DateTime),
    Column("completed_at", DateTime),
)


class IndexTaskConflict(Exception):
    pass


class IndexTasks:
    def __init__(self, repository: JobRepository) -> None:
        self.jobs = repository

    async def create(
        self, scope: OwnerScope, kb: str, document: str, retry_of: str | None = None
    ) -> RowMapping | None:
        async with self.jobs.factory.begin() as session:
            await session.execute(text("BEGIN IMMEDIATE"))
            scoped_document = (
                documents.c.id == document,
                documents.c.owner_user_id == scope.owner_user_id,
                documents.c.knowledge_base_id == kb,
                documents.c.deleted_at.is_(None),
            )
            if not await session.scalar(select(documents.c.id).where(*scoped_document)):
                return None
            latest = await self._get(session, scope, kb, document, None)
            if retry_of is not None and not await self._get(session, scope, kb, document, retry_of):
                return None
            if latest is not None and (
                latest["status"] in ("pending", "running") or retry_of is None
            ):
                raise IndexTaskConflict
            now = datetime.now(timezone.utc)
            task_id = str(uuid4())
            result = await session.execute(
                tasks.insert()
                .values(
                    id=task_id,
                    owner_user_id=scope.owner_user_id,
                    knowledge_base_id=kb,
                    document_id=document,
                    status="pending",
                    retry_of_task_id=retry_of,
                    created_at=now,
                    updated_at=now,
                )
                .returning(*tasks.c)
            )
            await self.jobs.enqueue(
                owner_user_id=scope.owner_user_id,
                kind=INDEX_TASK_KIND,
                resource_type=INDEX_TASK_KIND,
                resource_id=task_id,
                payload={},
                transaction=session,
            )
            await session.execute(
                update(documents).where(*scoped_document).values(index_status="pending")
            )
            return result.mappings().one()

    async def _get(
        self, session: AsyncSession, scope: OwnerScope, kb: str, document: str, task: str | None
    ) -> RowMapping | None:
        query = (
            select(tasks)
            .join(documents, documents.c.id == tasks.c.document_id)
            .where(
                tasks.c.owner_user_id == scope.owner_user_id,
                tasks.c.knowledge_base_id == kb,
                tasks.c.document_id == document,
                documents.c.owner_user_id == scope.owner_user_id,
                documents.c.knowledge_base_id == kb,
                documents.c.deleted_at.is_(None),
            )
        )
        if task is None:
            query = query.order_by(tasks.c.created_at.desc(), tasks.c.id).limit(1)
        else:
            query = query.where(tasks.c.id == task)
        return (await session.execute(query)).mappings().one_or_none()

    async def get(
        self, scope: OwnerScope, kb: str, document: str, task: str | None = None
    ) -> RowMapping | None:
        async with self.jobs.factory() as session:
            return await self._get(session, scope, kb, document, task)

    async def cancel(
        self, scope: OwnerScope, kb: str, document: str, task: str
    ) -> RowMapping | None:
        if await self.get(scope, kb, document, task) is None:
            return None
        async with self.jobs.factory() as session:
            job = await session.scalar(
                select(jobs.c.id).where(
                    jobs.c.owner_user_id == scope.owner_user_id,
                    jobs.c.resource_type == INDEX_TASK_KIND,
                    jobs.c.resource_id == task,
                )
            )
        if job is None:
            return None
        await self.jobs.cancel(str(job), owner_user_id=scope.owner_user_id)
        return await self.get(scope, kb, document, task)
