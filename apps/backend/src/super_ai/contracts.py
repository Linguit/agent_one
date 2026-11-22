from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class Meta(BaseModel):
    requestId: str


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    category: Literal["AUTH", "BUSINESS", "VALIDATION", "SYSTEM"]
    httpStatus: int
    message: str
    details: Any | None = None


class SuccessEnvelope(BaseModel):
    ok: Literal[True] = True
    data: Any
    meta: Meta


class FailureEnvelope(BaseModel):
    ok: Literal[False] = False
    error: ApiError
    meta: Meta


ERROR_CATALOG: dict[str, tuple[Literal["AUTH", "BUSINESS", "VALIDATION", "SYSTEM"], int, str]] = {
    "MCP_TIMEOUT": ("SYSTEM", 504, "MCP 操作超时。"),
    "MCP_DISCOVERY_FAILED": ("SYSTEM", 502, "MCP 连接或工具发现失败。"),
    "MCP_CALL_FAILED": ("SYSTEM", 502, "MCP 工具调用失败。"),
    "MCP_CONFIG_INVALID": ("SYSTEM", 500, "MCP 回退连接配置无效。"),
    "MCP_TOOL_NAME_CONFLICT": (
        "BUSINESS",
        409,
        "MCP 工具名称冲突，请调整服务器工具或禁用重复连接。",
    ),
    "CHAT_CONTEXT_LIMIT_REACHED": (
        "BUSINESS",
        409,
        "上下文已达到模型窗口的 95%，请手动压缩后重试。",
    ),
    "CHAT_MODEL_CAPABILITY_INVALID": (
        "SYSTEM",
        500,
        "modelCapabilities 缺少所选对话模型的有效 contextWindowTokens。",
    ),
    "CHAT_MEMORY_COMPACTION_FAILED": (
        "SYSTEM",
        502,
        "记忆压缩失败，原有历史与记忆保持不变，请重试。",
    ),
    "AUTH_INVALID_CREDENTIALS": ("AUTH", 401, "邮箱或密码错误。"),
    "AUTH_UNAUTHORIZED": ("AUTH", 401, "需要认证。"),
    "AUTH_FORBIDDEN": ("AUTH", 403, "无权访问该资源。"),
    "BUSINESS_NOT_FOUND": ("BUSINESS", 404, "请求的资源不存在。"),
    "BUSINESS_CONFLICT": ("BUSINESS", 409, "资源冲突。"),
    "VALIDATION_INVALID_REQUEST": ("VALIDATION", 422, "请求参数无效。"),
    "SYSTEM_INTERNAL_ERROR": ("SYSTEM", 500, "服务暂时不可用。"),
}


def request_id(request: Request) -> str:
    value = request.headers.get("X-Request-ID", "")
    try:
        UUID(value)
        return value
    except ValueError:
        return str(uuid4())


def success(data: Any, request: Request) -> JSONResponse:
    rid = getattr(request.state, "request_id", request_id(request))
    body = SuccessEnvelope(data=data, meta=Meta(requestId=rid))
    return JSONResponse(body.model_dump(by_alias=True))


def failure(code: str, request: Request, *, details: Any | None = None) -> JSONResponse:
    category, status, message = ERROR_CATALOG.get(code, ERROR_CATALOG["SYSTEM_INTERNAL_ERROR"])
    rid = getattr(request.state, "request_id", request_id(request))
    error = ApiError(
        code=code, category=category, httpStatus=status, message=message, details=details
    )
    body = FailureEnvelope(error=error, meta=Meta(requestId=rid))
    return JSONResponse(body.model_dump(by_alias=True), status_code=status)
