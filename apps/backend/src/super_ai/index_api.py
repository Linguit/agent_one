from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from sqlalchemy.engine import RowMapping
from starlette.responses import Response

from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.document_api import DOCUMENT_ERRORS, Owner, default_knowledge_base_id
from super_ai.document_contracts import DocumentEnvelope, DocumentIndexTask
from super_ai.job_api import get_job_repository
from super_ai.memory.sqlite.index_tasks import IndexTaskConflict, IndexTasks
from super_ai.memory.sqlite.jobs import JobRepository

router = APIRouter(
    prefix="/knowledge-bases/{kb}/documents/{document}/index-tasks",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={401: {"model": FailureEnvelope}, 500: {"model": FailureEnvelope}},
)
Repository = Annotated[JobRepository, Depends(get_job_repository)]


def _task(row: RowMapping) -> DocumentIndexTask:
    def utc(field: str) -> datetime | None:
        value = row[field]
        return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) else None

    return DocumentIndexTask.model_validate(
        {
            "id": row["id"],
            "knowledgeBaseId": row["knowledge_base_id"],
            "documentId": row["document_id"],
            "status": row["status"],
            "failureReason": row["failure_reason"],
            "retryOfTaskId": row["retry_of_task_id"],
            "createdAt": utc("created_at"),
            "updatedAt": utc("updated_at"),
            "startedAt": utc("started_at"),
            "completedAt": utc("completed_at"),
        }
    )


async def _create(
    kb: str,
    document: str,
    request: Request,
    scope: Owner,
    repository: Repository,
    retry_of: str | None = None,
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    try:
        row = await IndexTasks(repository).create(scope, kb, document, retry_of)
    except IndexTaskConflict:
        return failure("BUSINESS_CONFLICT", request)
    return _response(row, request)


def _response(row: RowMapping | None, request: Request) -> Response:
    if row is None:
        return failure("BUSINESS_NOT_FOUND", request)
    return success(_task(row).model_dump(mode="json"), request)


CREATE_ERRORS: dict[int | str, dict[str, object]] = {
    **DOCUMENT_ERRORS,
    409: {"model": FailureEnvelope},
}


@router.post("", response_model=DocumentEnvelope[DocumentIndexTask], responses=CREATE_ERRORS)
async def create_index_task(
    kb: str, document: str, request: Request, scope: Owner, repository: Repository
) -> Response:
    return await _create(kb, document, request, scope, repository)


@router.get(
    "", response_model=DocumentEnvelope[DocumentIndexTask | None], responses=DOCUMENT_ERRORS
)
async def latest_index_task(
    kb: str, document: str, request: Request, scope: Owner, repository: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    row = await IndexTasks(repository).get(scope, kb, document)
    return success(_task(row).model_dump(mode="json") if row is not None else None, request)


@router.get(
    "/{task}", response_model=DocumentEnvelope[DocumentIndexTask], responses=DOCUMENT_ERRORS
)
async def get_index_task(
    kb: str, document: str, task: str, request: Request, scope: Owner, repository: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    return _response(await IndexTasks(repository).get(scope, kb, document, task), request)


@router.post(
    "/{task}:retry", response_model=DocumentEnvelope[DocumentIndexTask], responses=CREATE_ERRORS
)
async def retry_index_task(
    kb: str, document: str, task: str, request: Request, scope: Owner, repository: Repository
) -> Response:
    return await _create(kb, document, request, scope, repository, task)


@router.post(
    "/{task}:cancel", response_model=DocumentEnvelope[DocumentIndexTask], responses=DOCUMENT_ERRORS
)
async def cancel_index_task(
    kb: str, document: str, task: str, request: Request, scope: Owner, repository: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    return _response(await IndexTasks(repository).cancel(scope, kb, document, task), request)
