"""真实告警输入；模块导入及应用启动均不访问外部服务。"""

import asyncio
import re
from typing import Literal, cast
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from pydantic import JsonValue as PydanticJsonValue

from super_ai.project_config import JsonObject, JsonValue


class BasicAuth(BaseModel):
    username: SecretStr
    password: SecretStr


class AlertSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    type: Literal["prometheus-v1", "alertmanager-v2"]
    url: str = Field(repr=False)
    basicAuth: BasicAuth | None = Field(default=None, repr=False)
    timeout: float = Field(default=10, gt=0, le=120)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("告警 API URL 无效")
        return value


class Alert(BaseModel):
    alertname: str
    service: str | None
    severity: str | None
    status: Literal["pending", "firing", "active", "suppressed", "unprocessed"]
    startsAt: str
    labels: dict[str, str]
    annotations: dict[str, str]
    source: str
    raw: dict[str, PydanticJsonValue]


class ActiveAlerts(BaseModel):
    items: list[Alert]


class AlertsUnavailable(Exception):
    """没有可用告警源；不携带上游错误或配置值。"""


def redact(value: JsonValue, secrets: tuple[str, ...] = ()) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if re.search(
                r"secret|password|token|authorization|api.?key|credential|cookie", key, re.I
            )
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", value)
        value = re.sub(
            r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)[^\s&,;]+",
            r"\1[REDACTED]",
            value,
        )
    return value


class AlertProvider:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def read(self, source: AlertSource, secrets: tuple[str, ...]) -> list[Alert]:
        auth = source.basicAuth
        response = await self.client.get(
            source.url,
            timeout=source.timeout,
            auth=httpx.BasicAuth(auth.username.get_secret_value(), auth.password.get_secret_value())
            if auth
            else None,
        )
        response.raise_for_status()
        payload = cast(JsonValue, response.json())
        if source.type == "prometheus-v1":
            if not isinstance(payload, dict) or payload.get("status") != "success":
                raise ValueError("告警响应无效")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError("告警响应无效")
            rows = data.get("alerts")
        else:
            rows = payload
        if not isinstance(rows, list):
            raise ValueError("告警响应无效")
        result: list[Alert] = []
        for original in rows:
            if not isinstance(original, dict):
                raise ValueError("告警记录无效")
            row = cast(JsonObject, redact(original, secrets))
            labels, annotations = row.get("labels"), row.get("annotations", {})
            if not isinstance(labels, dict) or not isinstance(annotations, dict):
                raise ValueError("告警标签无效")
            if not all(isinstance(v, str) for v in (*labels.values(), *annotations.values())):
                raise ValueError("告警标签无效")
            status = row.get("state") if source.type == "prometheus-v1" else row.get("status")
            if isinstance(status, dict):
                status = status.get("state")
            if status in ("inactive", "resolved"):
                continue
            result.append(
                Alert.model_validate(
                    {
                        "alertname": labels.get("alertname"),
                        "service": labels.get("service"),
                        "severity": labels.get("severity"),
                        "status": status,
                        "startsAt": row.get("activeAt")
                        if source.type == "prometheus-v1"
                        else row.get("startsAt"),
                        "labels": labels,
                        "annotations": annotations,
                        "source": redact(source.name, secrets),
                        "raw": row,
                    }
                )
            )
        return result


class AlertAggregator:
    def __init__(self, config: JsonObject, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self.transport = transport

    async def active(self) -> ActiveAlerts:
        section = self.config.get("prometheusAlerts", {})
        sources: JsonValue = section.get("sources") if isinstance(section, dict) else None
        if not isinstance(sources, list) or not sources:
            raise AlertsUnavailable
        valid: list[AlertSource] = []
        for source in sources:
            try:
                valid.append(AlertSource.model_validate(source))
            except (ValidationError, ValueError):
                continue
        secrets = tuple(
            value
            for source in valid
            if source.basicAuth
            for value in (
                source.basicAuth.username.get_secret_value(),
                source.basicAuth.password.get_secret_value(),
            )
            if value
        )
        async with httpx.AsyncClient(transport=self.transport, trust_env=False) as client:
            provider = AlertProvider(client)
            results = await asyncio.gather(
                *(provider.read(source, secrets) for source in valid), return_exceptions=True
            )
        successes = [result for result in results if isinstance(result, list)]
        if not successes:
            raise AlertsUnavailable
        return ActiveAlerts(items=[item for result in successes for item in result])
