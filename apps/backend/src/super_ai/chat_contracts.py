from datetime import datetime, timezone
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator
from pydantic.alias_generators import to_camel

from super_ai.contracts import Meta

ChatRole = Literal["user", "assistant", "system", "tool"]
DEFAULT_TITLE = "新会话"
TITLE_LIMIT = 80


class ChatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    references: list[dict[str, JsonValue]] = Field(default_factory=lambda: [])
    toolCallIds: list[str] = Field(default_factory=list)


class ChatStreamInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    metadata: ChatMetadata = Field(default_factory=ChatMetadata)

    @field_validator("content")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息内容不能为空白")
        return value


class ChatAppend(ChatStreamInput):
    role: ChatRole


class ToolCallAudit(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    owner_user_id: str
    chat_session_id: str | None
    diagnostic_task_id: str | None
    tool_name: str
    arguments: dict[str, JsonValue]
    status: Literal["started", "completed", "failed"]
    result_summary: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None

    @field_validator("started_at", "completed_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class ChatMessage(ChatAppend):
    id: str
    sessionId: str
    sequence: int = Field(ge=1)
    createdAt: datetime


class ChatSession(BaseModel):
    id: str
    title: str = Field(max_length=TITLE_LIMIT)
    createdAt: datetime
    updatedAt: datetime


class ChatDetail(BaseModel):
    session: ChatSession
    messages: list[ChatMessage]


class ChatAppended(BaseModel):
    session: ChatSession
    message: ChatMessage


class ChatDeleted(BaseModel):
    deleted: Literal[True] = True


T = TypeVar("T")


class ChatEnvelope(BaseModel, Generic[T]):
    ok: Literal[True]
    data: T
    meta: Meta
