from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    transport: Literal["sse", "streamable_http"]
    url: str = Field(min_length=1, max_length=4096)
    enabled: bool = True
    timeoutSeconds: int = Field(default=30, ge=1, le=300, strict=True)
    retries: int = Field(default=0, ge=0, le=5, strict=True)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("连接名称不能为空")
        return value.strip()

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in ("http", "https")
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not any(character.isspace() or ord(character) < 32 for character in value)
                and "\\" not in value
            )
            _ = parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("URL 必须为有 host、无 userinfo 的 http/https 地址")
        return value


class DiscoveredTool(BaseModel):
    name: str
    description: str
    inputSchema: dict[str, JsonValue]


class McpConnection(ConnectionInput):
    id: str
    owner: str
    lastCheck: datetime | None = None
    lastError: str | None = None
    discoveredTools: list[DiscoveredTool] = Field(default_factory=lambda: list[DiscoveredTool]())
    createdAt: datetime
    updatedAt: datetime

    @field_validator("lastCheck", "createdAt", "updatedAt")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None
