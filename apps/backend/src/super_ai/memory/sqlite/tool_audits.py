from datetime import datetime, timezone
from uuid import uuid4

from pydantic import JsonValue
from sqlalchemy import JSON, DateTime, Integer, String, column, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from super_ai.chat_contracts import ToolCallAudit
from super_ai.tenant import OwnerScope

audits = table(
    "agent_tool_call_audits",
    column("id", String),
    column("owner_user_id", String),
    column("chat_session_id", String),
    column("diagnostic_task_id", String),
    column("tool_name", String),
    column("arguments", JSON),
    column("status", String),
    column("result_summary", String),
    column("error_message", String),
    column("started_at", DateTime),
    column("completed_at", DateTime),
    column("duration_ms", Integer),
)


def chat_audits_filter(
    scope: OwnerScope, session_id: str
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    return (audits.c.owner_user_id == scope.owner_user_id, audits.c.chat_session_id == session_id)


class ToolAuditRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def start(
        self,
        scope: OwnerScope,
        tool_name: str,
        arguments: dict[str, JsonValue],
        *,
        chat_session_id: str | None = None,
        diagnostic_task_id: str | None = None,
    ) -> str:
        audit_id = str(uuid4())
        async with self._factory.begin() as db:
            if chat_session_id is not None:
                # Serialize against chat deletion even when SQLite foreign keys are disabled.
                await db.execute(text("BEGIN IMMEDIATE"))
                parent = await db.scalar(
                    text("SELECT id FROM chat_sessions WHERE owner_user_id = :owner AND id = :id"),
                    {"owner": scope.owner_user_id, "id": chat_session_id},
                )
                if parent is None:
                    raise LookupError("会话不存在或不可访问")
            await db.execute(
                audits.insert().values(
                    id=audit_id,
                    owner_user_id=scope.owner_user_id,
                    chat_session_id=chat_session_id,
                    diagnostic_task_id=diagnostic_task_id,
                    tool_name=tool_name,
                    arguments={key: "[REDACTED]" for key in arguments},
                    status="started",
                    started_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
        return audit_id

    async def finish(
        self,
        scope: OwnerScope,
        audit_id: str,
        duration_ms: int,
        *,
        result_summary: str | None = None,
        error_message: str | None = None,
    ) -> None:
        async with self._factory.begin() as db:
            result = await db.execute(
                audits.update()
                .where(
                    audits.c.id == audit_id,
                    audits.c.owner_user_id == scope.owner_user_id,
                    audits.c.status == "started",
                )
                .values(
                    status="failed" if error_message is not None else "completed",
                    result_summary=result_summary,
                    error_message=error_message,
                    completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    duration_ms=duration_ms,
                )
                .returning(audits.c.id)
            )
            if result.scalar_one_or_none() is None:
                raise LookupError("工具审计已结束或不可访问")

    async def list_chat(self, scope: OwnerScope, session_id: str) -> list[ToolCallAudit]:
        async with self._factory() as db:
            result = await db.execute(
                select(audits)
                .where(*chat_audits_filter(scope, session_id))
                .order_by(audits.c.started_at, audits.c.id)
            )
            return [ToolCallAudit.model_validate(row) for row in result.mappings()]
