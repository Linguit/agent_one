from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class PersistenceRecord:
    id: UUID
    created_at: datetime
    payload: dict[str, Any]


class Repository(Protocol):
    async def add(self, record: PersistenceRecord) -> PersistenceRecord: ...
    async def get(self, record_id: UUID) -> PersistenceRecord | None: ...
