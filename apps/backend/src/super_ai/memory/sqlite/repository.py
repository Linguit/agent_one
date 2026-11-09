from datetime import timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.memory.base import persistence_probe
from super_ai.memory.repository import PersistenceRecord, Repository


class SqliteRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: PersistenceRecord) -> PersistenceRecord:
        await self._session.execute(
            persistence_probe.insert().values(
                id=str(record.id), created_at=record.created_at, payload=record.payload
            )
        )
        return record

    async def get(self, record_id: UUID) -> PersistenceRecord | None:
        result = await self._session.execute(
            select(persistence_probe).where(persistence_probe.c.id == str(record_id))
        )
        row = result.mappings().first()
        if row is None:
            return None
        payload = row["payload"]
        normalized = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
        return PersistenceRecord(
            id=UUID(row["id"]),
            created_at=row["created_at"].replace(tzinfo=timezone.utc),
            payload=normalized,
        )
