from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from super_ai.agent_chat import ChatAgent, ChatModelFactory
from super_ai.auth import AuthService, current_user, get_auth_service
from super_ai.chat_api import router as chat_router
from super_ai.configuration_api import router as configuration_router
from super_ai.contracts import failure, success
from super_ai.document_api import router as document_router
from super_ai.document_indexing import DocumentIndexer
from super_ai.index_api import router as index_router
from super_ai.job_api import router as job_router
from super_ai.job_runtime import JobHandlers, JobWorker
from super_ai.knowledge_retrieval import KnowledgeRetrieval
from super_ai.llm_provider import create_llm_provider
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.engine import create_engine, session_factory
from super_ai.memory.sqlite.chat import ChatRepository
from super_ai.memory.sqlite.configuration import ConfigurationRepository
from super_ai.memory.sqlite.documents import DeleteVectors, DocumentRepository
from super_ai.memory.sqlite.index_tasks import INDEX_TASK_KIND
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.memory.sqlite.tool_audits import ToolAuditRepository
from super_ai.project_config import JsonObject, load_project_config
from super_ai.session_memory import MemoryFailure, SessionMemory
from super_ai.tenant import OwnerScope
from super_ai.vector_store import MilvusVectorStore, VectorStoreConfig

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


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


def create_app(
    *,
    config: JsonObject | None = None,
    config_dir: Path | None = None,
    job_handlers: JobHandlers | None = None,
    delete_document_vectors: DeleteVectors | None = None,
    chat_model_factory: ChatModelFactory | None = None,
) -> FastAPI:
    if config is not None and config_dir is not None:
        raise ValueError("config 与 config_dir 不能同时指定")
    project_config = deepcopy(config) if config is not None else load_project_config(config_dir)
    database_config = cast(dict[str, object], project_config.get("database", {}))
    db_url = cast(str, database_config.get("url", "sqlite+aiosqlite:///./super_ai.db"))

    def delete_vectors(scope: OwnerScope, kb: str, document: str) -> object:
        store = MilvusVectorStore(VectorStoreConfig.from_project(project_config))
        return store.delete_existing_document(scope, kb, document)

    @asynccontextmanager
    async def open_chat_model() -> AsyncGenerator["BaseChatModel"]:
        async with create_llm_provider(project_config) as provider:
            yield provider.chat_model

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        engine = create_engine(DatabaseSettings(url=db_url))
        try:
            factory = session_factory(engine)
            repository = JobRepository(factory)
            app.state.db_engine = engine
            app.state.db_session_factory = factory
            app.state.job_repository = repository
            chat = ChatRepository(factory)
            audits = ToolAuditRepository(factory)
            app.state.chat_repository = chat
            app.state.tool_audits = audits
            configuration = ConfigurationRepository(factory)
            app.state.chat_configuration = configuration
            memory = SessionMemory(
                chat, configuration, chat_model_factory or open_chat_model, project_config
            )
            app.state.session_memory = memory
            chat.prepare_append = memory.prepare_append
            app.state.document_repository = DocumentRepository(
                factory, delete_document_vectors or delete_vectors
            )
            knowledge = KnowledgeRetrieval(
                factory,
                lambda: create_llm_provider(project_config),
                lambda: MilvusVectorStore(VectorStoreConfig.from_project(project_config)),
            )
            app.state.knowledge_retrieval = knowledge
            app.state.chat_agent = ChatAgent(
                chat_model_factory or open_chat_model,
                knowledge.tool,
                chat,
                audits,
                configuration,
                memory,
            )
            handlers = JobHandlers()
            if job_handlers is not None:
                for kind in job_handlers.kinds():
                    handlers.register(kind, job_handlers.get(kind))
            if INDEX_TASK_KIND not in handlers.kinds():
                indexer = DocumentIndexer(
                    app.state.document_repository,
                    lambda: create_llm_provider(project_config),
                    lambda: MilvusVectorStore(VectorStoreConfig.from_project(project_config)),
                )
                handlers.register(INDEX_TASK_KIND, indexer.run)
            async with JobWorker(repository, handlers):
                yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Super AI 基础服务", lifespan=lifespan)
    app.state.project_config = project_config
    app.include_router(job_router)
    app.include_router(chat_router)
    app.include_router(configuration_router)
    app.include_router(document_router)
    app.include_router(index_router)
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
        response = failure("SYSTEM_INTERNAL_ERROR", request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(MemoryFailure)
    async def memory_handler(request: Request, exc: MemoryFailure) -> JSONResponse:
        return failure(exc.code, request)

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
