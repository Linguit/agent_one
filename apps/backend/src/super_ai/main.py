from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from super_ai.auth import AuthService, current_user, get_auth_service
from super_ai.contracts import failure, success
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine, session_factory
from super_ai.project_config import JsonObject, load_project_config


#   定义一个会包住所有请求的中间件
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        value = request.headers.get("X-Request-ID", "")
        try:
            UUID(value)
            request.state.request_id = value
        except ValueError:
            request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def get_project_config(request: Request) -> JsonObject:
    return cast(JsonObject, request.app.state.project_config)


def create_app(*, config: JsonObject | None = None, config_dir: Path | None = None) -> FastAPI:
    if config is not None and config_dir is not None:
        raise ValueError("config 与 config_dir 不能同时指定")
    project_config = deepcopy(config) if config is not None else load_project_config(config_dir)
    app = FastAPI(title="Super AI 基础服务")
    app.state.project_config = project_config
    database_config = cast(dict[str, object], project_config.get("database", {}))
    db_url = cast(str, database_config.get("url", "sqlite+aiosqlite:///./super_ai.db"))
    app.state.db_engine = create_engine(DatabaseSettings(url=db_url))
    app.state.db_session_factory = session_factory(app.state.db_engine)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(error["loc"]), "message": error["msg"]} for error in exc.errors()]
        return failure("VALIDATION_INVALID_REQUEST", request, details=details)

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
        del exc
        return failure("SYSTEM_INTERNAL_ERROR", request)

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = (
            "AUTH_INVALID_CREDENTIALS"
            if exc.detail == "AUTH_INVALID_CREDENTIALS"
            else ("AUTH_UNAUTHORIZED" if exc.status_code == 401 else "BUSINESS_NOT_FOUND")
        )
        return failure(code, request)

    class AuthRequest(BaseModel):
        email: str
        password: str

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        return success({"status": "ok"}, request)

    @app.post("/auth/register")
    async def register(
        body: AuthRequest, request: Request, service: AuthService = Depends(get_auth_service)
    ) -> JSONResponse:
        return success(await service.register(str(body.email), body.password), request)

    @app.post("/auth/login")
    async def login(
        body: AuthRequest, request: Request, service: AuthService = Depends(get_auth_service)
    ) -> JSONResponse:
        token, user = await service.login(str(body.email), body.password)
        return success({"token": token, "user": user}, request)

    @app.post("/auth/logout")
    async def logout(
        request: Request,
        user: dict[str, str] = Depends(current_user),
        service: AuthService = Depends(get_auth_service),
    ) -> JSONResponse:
        del user
        await service.logout(request.headers["Authorization"][7:])
        return success({"loggedOut": True}, request)

    @app.get("/auth/me")
    async def me(request: Request, user: dict[str, str] = Depends(current_user)) -> JSONResponse:
        return success(user, request)

    return app
