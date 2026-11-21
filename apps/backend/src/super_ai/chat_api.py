from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from pydantic import JsonValue
from starlette.responses import Response, StreamingResponse

from super_ai.agent_chat import ChatAgent
from super_ai.auth import current_user
from super_ai.chat_contracts import (
    ChatAppend,
    ChatAppended,
    ChatCreate,
    ChatDeleted,
    ChatDetail,
    ChatEnvelope,
    ChatMemoryUpdate,
    ChatMessage,
    ChatMetadata,
    ChatSession,
    ChatStreamInput,
    ToolCallAudit,
)
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.memory.sqlite.chat import (
    ChatAccessDenied,
    ChatRepository,
    MessageRecord,
    SessionRecord,
)
from super_ai.memory.sqlite.tool_audits import ToolAuditRepository
from super_ai.session_memory import SessionMemory
from super_ai.tenant import OwnerScope


def _owner(user: Annotated[dict[str, str], Depends(current_user)]) -> OwnerScope:
    return OwnerScope(user["id"], user["id"])


def _repository(request: Request) -> ChatRepository:
    return cast(ChatRepository, request.app.state.chat_repository)


async def _session(request: Request, scope: OwnerScope, record: SessionRecord) -> ChatSession:
    return await cast(SessionMemory, request.app.state.session_memory).state(scope, record.id)


def _message(record: MessageRecord) -> ChatMessage:
    return ChatMessage(
        id=record.id,
        sessionId=record.session_id,
        role=record.role,
        content=record.content,
        sequence=record.sequence,
        createdAt=record.created_at,
        metadata=ChatMetadata.model_validate(record.metadata),
    )


Owner = Annotated[OwnerScope, Depends(_owner)]
Repository = Annotated[ChatRepository, Depends(_repository)]
FORBIDDEN: dict[int | str, dict[str, object]] = {403: {"model": FailureEnvelope}}
VALIDATION: dict[int | str, dict[str, object]] = {422: {"model": FailureEnvelope}}
router = APIRouter(
    prefix="/chat/sessions",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={401: {"model": FailureEnvelope}, 500: {"model": FailureEnvelope}},
)


@router.get(
    "/{id}/tool-call-audits", response_model=ChatEnvelope[list[ToolCallAudit]], responses=FORBIDDEN
)
async def tool_call_audits(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    try:
        await repo.require_session(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    audits = cast(ToolAuditRepository, request.app.state.tool_audits)
    return success(
        [row.model_dump(mode="json", by_alias=True) for row in await audits.list_chat(scope, id)],
        request,
    )


@router.post(
    "/{id}/messages:stream",
    response_model=None,
    responses={**FORBIDDEN, **VALIDATION, 200: {"content": {"text/event-stream": {}}}},
)
async def stream_message(
    id: str, request: Request, scope: Owner, repo: Repository, body: ChatStreamInput
) -> Response:
    try:
        _, user = await repo.append(
            scope,
            id,
            role="user",
            content=body.content,
            metadata=cast(dict[str, JsonValue], body.metadata.model_dump(mode="json")),
        )
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    agent = cast(ChatAgent, request.app.state.chat_agent)
    return StreamingResponse(
        agent.stream(scope, user, cast(str, request.state.request_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=ChatEnvelope[ChatSession], responses=VALIDATION)
async def create(
    request: Request, scope: Owner, repo: Repository, body: ChatCreate | None = None
) -> Response:
    # 配置错误应在新建会话之前暴露。
    cast(SessionMemory, request.app.state.session_memory).window()
    return success(
        (await _session(request, scope, await repo.create(scope))).model_dump(mode="json"), request
    )


@router.get("", response_model=ChatEnvelope[list[ChatSession]])
async def list_sessions(request: Request, scope: Owner, repo: Repository) -> Response:
    return success(
        [
            (await _session(request, scope, row)).model_dump(mode="json")
            for row in await repo.list_sessions(scope)
        ],
        request,
    )


@router.get("/{id}", response_model=ChatEnvelope[ChatDetail], responses=FORBIDDEN)
async def detail(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    try:
        session, messages = await repo.detail(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    data = ChatDetail(
        session=await _session(request, scope, session),
        messages=[_message(row) for row in messages],
    )
    return success(data.model_dump(mode="json"), request)


@router.post(
    "/{id}/messages",
    response_model=ChatEnvelope[ChatAppended],
    responses={**FORBIDDEN, **VALIDATION},
)
async def append(
    id: str, body: ChatAppend, request: Request, scope: Owner, repo: Repository
) -> Response:
    try:
        session, message = await repo.append(
            scope,
            id,
            role=body.role,
            content=body.content,
            metadata=cast(dict[str, JsonValue], body.metadata.model_dump(mode="json")),
        )
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    data = ChatAppended(session=await _session(request, scope, session), message=_message(message))
    return success(data.model_dump(mode="json"), request)


@router.post("/{id}/messages:clear", response_model=ChatEnvelope[ChatDetail], responses=FORBIDDEN)
async def clear(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    try:
        session = await repo.clear(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(
        ChatDetail(session=await _session(request, scope, session), messages=[]).model_dump(
            mode="json"
        ),
        request,
    )


@router.delete("/{id}", response_model=ChatEnvelope[ChatDeleted], responses=FORBIDDEN)
async def delete(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    try:
        await repo.delete(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(ChatDeleted().model_dump(mode="json"), request)


@router.put(
    "/{id}/memory", response_model=ChatEnvelope[ChatSession], responses={**FORBIDDEN, **VALIDATION}
)
async def update_memory(
    id: str, body: ChatMemoryUpdate, request: Request, scope: Owner, repo: Repository
) -> Response:
    try:
        await repo.require_session(scope, id)
        state = await cast(SessionMemory, request.app.state.session_memory).state(
            scope, id, mode=body.memoryMode
        )
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(state.model_dump(mode="json"), request)


@router.post("/{id}/memory:compact", response_model=ChatEnvelope[ChatSession], responses=FORBIDDEN)
async def compact_memory(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    try:
        await repo.require_session(scope, id)
        state = await cast(SessionMemory, request.app.state.session_memory).state(
            scope, id, compact=True
        )
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(state.model_dump(mode="json"), request)
