from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from starlette.responses import Response

from super_ai.chat_api import Owner
from super_ai.chat_contracts import ChatDeleted, ChatEnvelope
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.mcp_contracts import ConnectionInput, McpConnection
from super_ai.mcp_provider import McpProvider
from super_ai.memory.sqlite.chat import ChatAccessDenied
from super_ai.memory.sqlite.mcp import McpConnectionConflict


def _provider(request: Request) -> McpProvider:
    return cast(McpProvider, request.app.state.mcp_provider)


Provider = Annotated[McpProvider, Depends(_provider)]
router = APIRouter(
    prefix="/mcp/connections",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={status: {"model": FailureEnvelope} for status in (401, 403, 409, 422, 500)},
)


@router.get("", response_model=ChatEnvelope[list[McpConnection]])
async def list_connections(request: Request, scope: Owner, provider: Provider) -> Response:
    rows = await provider.repository.list(scope)
    return success([row.model_dump(mode="json") for row in rows], request)


@router.post("", response_model=ChatEnvelope[McpConnection])
async def create_connection(
    body: ConnectionInput, request: Request, scope: Owner, provider: Provider
) -> Response:
    try:
        record = await provider.repository.save(scope, body)
    except McpConnectionConflict:
        return failure("BUSINESS_CONFLICT", request)
    return success(record.model_dump(mode="json"), request)


@router.put("/{id}", response_model=ChatEnvelope[McpConnection])
async def update_connection(
    id: str, body: ConnectionInput, request: Request, scope: Owner, provider: Provider
) -> Response:
    try:
        record = await provider.repository.save(scope, body, id)
    except McpConnectionConflict:
        return failure("BUSINESS_CONFLICT", request)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(record.model_dump(mode="json"), request)


@router.delete("/{id}", response_model=ChatEnvelope[ChatDeleted])
async def delete_connection(
    id: str, request: Request, scope: Owner, provider: Provider
) -> Response:
    try:
        await provider.repository.delete(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(ChatDeleted().model_dump(), request)


@router.post("/{id}:check", response_model=ChatEnvelope[McpConnection])
async def check_connection(id: str, request: Request, scope: Owner, provider: Provider) -> Response:
    try:
        record = await provider.check(scope, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(record.model_dump(mode="json"), request)
