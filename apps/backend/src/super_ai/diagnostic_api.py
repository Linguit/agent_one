import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from starlette.responses import Response, StreamingResponse

from super_ai.chat_api import Owner
from super_ai.chat_contracts import ChatEnvelope
from super_ai.contracts import ERROR_CATALOG, failure, success
from super_ai.diagnostic_contracts import DiagnosticInput, StreamInput
from super_ai.diagnostic_runtime import DiagnosticRunner
from super_ai.memory.sqlite.diagnostics import Diagnostics
from super_ai.project_config import JsonObject

router = APIRouter(
    prefix="/aiops/diagnostics", dependencies=[Depends(HTTPBearer(auto_error=False))]
)


def repository(request: Request) -> Diagnostics:
    return cast(Diagnostics, request.app.state.diagnostics)


Repository = Annotated[Diagnostics, Depends(repository)]


@router.post("", response_model=ChatEnvelope[dict[str, object]])
async def create(
    request: Request,
    scope: Owner,
    repo: Repository,
    body: DiagnosticInput,
) -> Response:
    runner = cast(DiagnosticRunner, request.app.state.diagnostic_runner)
    safe = DiagnosticInput.model_validate(runner.clean(body))
    return success(await repo.create(scope, safe), request)


@router.get("", response_model=ChatEnvelope[list[dict[str, object]]])
async def list_tasks(request: Request, scope: Owner, repo: Repository) -> Response:
    return success(await repo.list(scope), request)


@router.get("/{id}", response_model=ChatEnvelope[dict[str, object]])
async def detail(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    row = await repo.detail(scope, id)
    return success(row, request) if row else failure("BUSINESS_NOT_FOUND", request)


@router.get("/{id}/evidence-chain", response_model=ChatEnvelope[dict[str, object]])
async def evidence_chain(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    if await repo.detail(scope, id) is None:
        return failure("BUSINESS_NOT_FOUND", request)
    return success(await repo.chain(scope, id), request)


def frame(job_id: str, sequence: int, kind: str, data: JsonObject, timestamp: datetime) -> str:
    event_id = f"{job_id}:{sequence}"
    payload = json.dumps(
        {
            "id": event_id,
            "sequence": sequence,
            "type": kind,
            "channel": "aiops",
            "timestamp": timestamp.isoformat(),
            "data": data,
        },
        ensure_ascii=False,
    )
    return f"id: {event_id}\nevent: {kind}\ndata: {payload}\n\n"


@router.post("/{id}:stream", response_model=None)
async def stream(
    id: str,
    request: Request,
    scope: Owner,
    repo: Repository,
    body: StreamInput,
) -> Response:
    if await repo.detail(scope, id) is None:
        return failure("BUSINESS_NOT_FOUND", request)
    job = (
        await repo.jobs.get(body.jobId, owner_user_id=scope.owner_user_id)
        if body.jobId
        else (await repo.latest_job(scope, id))
    )
    if job is None or job["resource_id"] != id or job["resource_type"] != "diagnostic_task":
        return failure("BUSINESS_NOT_FOUND", request)
    after = body.afterSequence
    resume = request.headers.get("Last-Event-ID")
    if resume:
        prefix, _, sequence = resume.rpartition(":")
        if prefix != job["id"] or not sequence.isdigit():
            return failure("VALIDATION_INVALID_REQUEST", request)
        after = max(after, int(sequence))

    async def events() -> AsyncGenerator[str]:
        cursor = after
        while True:
            rows = await repo.jobs.list_events(
                str(job["id"]),
                owner_user_id=scope.owner_user_id,
                after_sequence=cursor,
            )
            for row in rows:
                cursor = int(row["sequence"])
                kind = str(row["kind"])
                data = cast(JsonObject, row["data"])
                if kind in ("queued", "running", "retry_scheduled", "cancel_requested"):
                    status = (
                        "queued"
                        if kind == "retry_scheduled"
                        else ("running" if kind == "cancel_requested" else kind)
                    )
                    kind, data = (
                        "task.status",
                        {
                            "status": status,
                            "task": {"message": "后台诊断状态更新。", "progress": 0},
                        },
                    )
                elif kind == "diagnostic.error":
                    # A retry may recover; errors become terminal only at persisted failed state.
                    kind, data = (
                        "task.status",
                        {
                            "status": "running",
                            "task": {
                                "message": str(data["code"]),
                                "progress": 0,
                            },
                        },
                    )
                elif kind == "succeeded":
                    kind, data = "complete", {"result": {"status": "succeeded"}}
                elif kind in ("failed", "cancelled"):
                    if kind == "cancelled":
                        kind, data = "complete", {"result": {"status": "cancelled"}}
                    else:
                        history = await repo.jobs.list_events(
                            str(job["id"]),
                            owner_user_id=scope.owner_user_id,
                        )
                        errors = [event for event in history if event["kind"] == "diagnostic.error"]
                        code = (
                            str(errors[-1]["data"]["code"])
                            if errors
                            else "DIAGNOSTIC_EXECUTION_FAILED"
                        )
                        category, http_status, message = ERROR_CATALOG.get(
                            code,
                            ERROR_CATALOG["DIAGNOSTIC_EXECUTION_FAILED"],
                        )
                        kind, data = (
                            "error",
                            {
                                "error": {
                                    "code": code,
                                    "category": category,
                                    "httpStatus": http_status,
                                    "message": message,
                                },
                                "meta": {"requestId": str(request.state.request_id)},
                            },
                        )
                yield frame(str(job["id"]), cursor, kind, cast(JsonObject, data), row["created_at"])
            current = await repo.jobs.get(str(job["id"]), owner_user_id=scope.owner_user_id)
            if current is None or current["status"] in ("succeeded", "failed", "cancelled"):
                # One extra read closes the finish/read race without inventing an event.
                more = await repo.jobs.list_events(
                    str(job["id"]),
                    owner_user_id=scope.owner_user_id,
                    after_sequence=cursor,
                )
                if not more:
                    return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
