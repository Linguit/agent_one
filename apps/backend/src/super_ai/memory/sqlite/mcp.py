from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, column, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.mcp_contracts import ConnectionInput, DiscoveredTool, McpConnection
from super_ai.memory.sqlite.chat import ChatAccessDenied
from super_ai.tenant import OwnerScope

connections = table(
    "mcp_connections",
    *[column(name, String) for name in ("id", "owner", "name", "transport", "url", "lastError")],
    column("enabled", Boolean),
    column("timeoutSeconds", Integer),
    column("retries", Integer),
    column("lastCheck", DateTime),
    column("discoveredTools", JSON),
    column("createdAt", DateTime),
    column("updatedAt", DateTime),
)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class McpConnectionConflict(ValueError):
    pass


class McpRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def list(self, scope: OwnerScope) -> list[McpConnection]:
        async with self._factory() as db:
            result = await db.execute(
                select(connections)
                .where(connections.c.owner == scope.owner_user_id)
                .order_by(connections.c.createdAt, connections.c.id)
            )
            return [McpConnection.model_validate(row) for row in result.mappings()]

    async def get(self, scope: OwnerScope, id: str) -> McpConnection:
        async with self._factory() as db:
            row = (
                (
                    await db.execute(
                        select(connections).where(
                            connections.c.owner == scope.owner_user_id, connections.c.id == id
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ChatAccessDenied
            return McpConnection.model_validate(row)

    async def save(
        self, scope: OwnerScope, body: ConnectionInput, id: str | None = None
    ) -> McpConnection:
        timestamp = now()
        values: dict[str, Any] = {
            **body.model_dump(),
            "updatedAt": timestamp,
            "lastCheck": None,
            "lastError": None,
            "discoveredTools": [],
        }
        async with self._factory.begin() as db:
            # Serialize duplicate checks and writes, including concurrent POST requests.
            await db.execute(text("BEGIN IMMEDIATE"))
            if id is not None:
                existing = await db.scalar(
                    select(connections.c.id).where(
                        connections.c.owner == scope.owner_user_id, connections.c.id == id
                    )
                )
                if existing is None:
                    raise ChatAccessDenied
            duplicate = select(connections.c.id).where(
                connections.c.owner == scope.owner_user_id,
                connections.c.transport == body.transport,
                connections.c.url == body.url,
            )
            if id is not None:
                duplicate = duplicate.where(connections.c.id != id)
            if await db.scalar(duplicate) is not None:
                raise McpConnectionConflict
            if id is None:
                id = str(uuid4())
                await db.execute(
                    connections.insert().values(
                        id=id, owner=scope.owner_user_id, createdAt=timestamp, **values
                    )
                )
            else:
                result = await db.execute(
                    connections.update()
                    .where(connections.c.owner == scope.owner_user_id, connections.c.id == id)
                    .values(**values)
                    .returning(connections.c.id)
                )
                if result.scalar_one_or_none() is None:
                    raise ChatAccessDenied
        return await self.get(scope, id)

    async def delete(self, scope: OwnerScope, id: str) -> None:
        async with self._factory.begin() as db:
            result = await db.execute(
                connections.delete()
                .where(connections.c.owner == scope.owner_user_id, connections.c.id == id)
                .returning(connections.c.id)
            )
            if result.scalar_one_or_none() is None:
                raise ChatAccessDenied

    async def checked(
        self,
        scope: OwnerScope,
        record: McpConnection,
        tools: list[DiscoveredTool],
        error: str | None,
    ) -> McpConnection:
        async with self._factory.begin() as db:
            await db.execute(
                connections.update()
                .where(
                    connections.c.owner == scope.owner_user_id,
                    connections.c.id == record.id,
                    connections.c.updatedAt == record.updatedAt.replace(tzinfo=None),
                )
                .values(
                    lastCheck=now(),
                    lastError=error,
                    discoveredTools=[tool.model_dump(mode="json") for tool in tools],
                )
            )
        return await self.get(scope, record.id)
