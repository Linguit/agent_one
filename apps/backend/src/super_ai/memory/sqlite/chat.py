from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import uuid4

from pydantic import JsonValue
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, column, select, table, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.chat_contracts import DEFAULT_TITLE, TITLE_LIMIT, ChatRole
from super_ai.tenant import OwnerScope

sessions = table(
    "chat_sessions",
    column("id", String),
    column("owner_user_id", String),
    column("title", String),
    column("created_at", DateTime),
    column("updated_at", DateTime),
    column("last_sequence", Integer),
    column("has_user_message", Boolean),
)
messages = table(
    "chat_messages",
    column("id", String),
    column("owner_user_id", String),
    column("session_id", String),
    column("role", String),
    column("content", String),
    column("metadata", JSON),
    column("sequence", Integer),
    column("created_at", DateTime),
)


class ChatAccessDenied(Exception):
    pass


@dataclass(frozen=True)
class SessionRecord:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: str
    session_id: str
    role: ChatRole
    content: str
    metadata: dict[str, JsonValue]
    sequence: int
    created_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _session_record(row: RowMapping) -> SessionRecord:
    return SessionRecord(
        row["id"],
        row["title"],
        row["created_at"].replace(tzinfo=timezone.utc),
        row["updated_at"].replace(tzinfo=timezone.utc),
    )


def _message_record(row: RowMapping) -> MessageRecord:
    return MessageRecord(
        row["id"],
        row["session_id"],
        row["role"],
        row["content"],
        row["metadata"],
        row["sequence"],
        row["created_at"].replace(tzinfo=timezone.utc),
    )


class ChatRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    @asynccontextmanager
    async def _transaction(self, *, write: bool) -> AsyncGenerator[AsyncSession, None]:
        async with self._factory.begin() as db:
            # SQLite's driver does not begin a transaction for SELECT by default.
            await db.execute(text("BEGIN IMMEDIATE" if write else "BEGIN"))
            yield db

    async def _require(self, db: AsyncSession, scope: OwnerScope, session_id: str) -> RowMapping:
        result = await db.execute(
            select(sessions).where(
                sessions.c.owner_user_id == scope.owner_user_id, sessions.c.id == session_id
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ChatAccessDenied
        return row

    async def create(self, scope: OwnerScope) -> SessionRecord:
        now = _now()
        async with self._factory.begin() as db:
            result = await db.execute(
                sessions.insert()
                .values(
                    id=str(uuid4()),
                    owner_user_id=scope.owner_user_id,
                    title=DEFAULT_TITLE,
                    created_at=now,
                    updated_at=now,
                    last_sequence=0,
                    has_user_message=False,
                )
                .returning(*sessions.c)
            )
            return _session_record(result.mappings().one())

    async def list_sessions(self, scope: OwnerScope) -> list[SessionRecord]:
        async with self._factory() as db:
            rows = await db.execute(
                select(sessions)
                .where(sessions.c.owner_user_id == scope.owner_user_id)
                .order_by(sessions.c.updated_at.desc(), sessions.c.id.desc())
            )
            return [_session_record(row) for row in rows.mappings()]

    async def detail(
        self, scope: OwnerScope, session_id: str
    ) -> tuple[SessionRecord, list[MessageRecord]]:
        async with self._transaction(write=False) as db:
            row = await self._require(db, scope, session_id)
            result = await db.execute(
                select(messages)
                .where(
                    messages.c.owner_user_id == scope.owner_user_id,
                    messages.c.session_id == session_id,
                )
                .order_by(messages.c.sequence)
            )
            return _session_record(row), [_message_record(item) for item in result.mappings()]

    async def append(
        self,
        scope: OwnerScope,
        session_id: str,
        *,
        role: ChatRole,
        content: str,
        metadata: dict[str, JsonValue],
    ) -> tuple[SessionRecord, MessageRecord]:
        async with self._transaction(write=True) as db:
            row = await self._require(db, scope, session_id)
            sequence = cast(int, row["last_sequence"]) + 1
            now = max(_now(), cast(datetime, row["updated_at"]) + timedelta(microseconds=1))
            first_user = role == "user" and not row["has_user_message"]
            title = " ".join(content.split())[:TITLE_LIMIT] if first_user else row["title"]
            updated = await db.execute(
                sessions.update()
                .where(sessions.c.owner_user_id == scope.owner_user_id, sessions.c.id == session_id)
                .values(
                    title=title,
                    updated_at=now,
                    last_sequence=sequence,
                    has_user_message=bool(row["has_user_message"]) or first_user,
                )
                .returning(*sessions.c)
            )
            inserted = await db.execute(
                messages.insert()
                .values(
                    id=str(uuid4()),
                    owner_user_id=scope.owner_user_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    metadata=metadata,
                    sequence=sequence,
                    created_at=now,
                )
                .returning(*messages.c)
            )
            return _session_record(updated.mappings().one()), _message_record(
                inserted.mappings().one()
            )

    async def _remove_messages(self, db: AsyncSession, scope: OwnerScope, session_id: str) -> None:
        await db.execute(
            messages.delete().where(
                messages.c.owner_user_id == scope.owner_user_id, messages.c.session_id == session_id
            )
        )

    async def clear(self, scope: OwnerScope, session_id: str) -> SessionRecord:
        async with self._transaction(write=True) as db:
            row = await self._require(db, scope, session_id)
            await self._remove_messages(db, scope, session_id)
            now = max(_now(), cast(datetime, row["updated_at"]) + timedelta(microseconds=1))
            updated = await db.execute(
                sessions.update()
                .where(sessions.c.owner_user_id == scope.owner_user_id, sessions.c.id == session_id)
                .values(
                    title=DEFAULT_TITLE, updated_at=now, last_sequence=0, has_user_message=False
                )
                .returning(*sessions.c)
            )
            return _session_record(updated.mappings().one())

    async def delete(self, scope: OwnerScope, session_id: str) -> None:
        async with self._transaction(write=True) as db:
            await self._require(db, scope, session_id)
            await self._remove_messages(db, scope, session_id)
            await db.execute(
                sessions.delete().where(
                    sessions.c.owner_user_id == scope.owner_user_id, sessions.c.id == session_id
                )
            )
