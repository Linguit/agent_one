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
    "AUTH_INVALID_CREDENTIALS": ("AUTH", 401, "邮箱或密码错误。"),
    "AUTH_UNAUTHORIZED": ("AUTH", 401, "需要认证。"),
    "AUTH_FORBIDDEN": ("AUTH", 403, "无权访问该资源。"),
    "BUSINESS_NOT_FOUND": ("BUSINESS", 404, "请求的资源不存在。"),
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
