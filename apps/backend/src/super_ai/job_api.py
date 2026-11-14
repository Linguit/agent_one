from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.engine import RowMapping
from starlette.responses import Response

from super_ai.auth import current_user
from super_ai.contracts import FailureEnvelope, Meta, failure, success
from super_ai.memory.sqlite.jobs import JobRepository

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
T = TypeVar("T")


class BackgroundJob(BaseModel):
    id: str
    kind: str
    resourceType: str
    resourceId: str
    status: JobStatus
    attempt: int
    maxAttempts: int
    timeoutSeconds: int
    availableAt: datetime
    leaseExpiresAt: datetime | None
    cancelRequestedAt: datetime | None
    retryOfJobId: str | None
    errorMessage: str | None
    createdAt: datetime
    updatedAt: datetime
    startedAt: datetime | None
    completedAt: datetime | None

    @classmethod
    def from_row(cls, row: RowMapping) -> "BackgroundJob":
        data: dict[str, object] = {}
        for name in cls.model_fields:
            column = "".join(
                f"_{letter.lower()}" if letter.isupper() else letter for letter in name
            )
            value = row[column]
            if isinstance(value, datetime):
                value = value.replace(tzinfo=timezone.utc)
            data[name] = value
        return cls.model_validate(data)


class BackgroundJobEnvelope(BaseModel, Generic[T]):
    ok: Literal[True]
    data: T
    meta: Meta


def get_job_repository(request: Request) -> JobRepository:
    return cast(JobRepository, request.app.state.job_repository)


router = APIRouter(
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={401: {"model": FailureEnvelope}, 500: {"model": FailureEnvelope}},
)
Repository = Annotated[JobRepository, Depends(get_job_repository)]
User = Annotated[dict[str, str], Depends(current_user)]
not_found: dict[int | str, dict[str, object]] = {404: {"model": FailureEnvelope}}


def _response(row: RowMapping | None, request: Request) -> Response:
    if row is None:
        return failure("BUSINESS_NOT_FOUND", request)
    return success(BackgroundJob.from_row(row).model_dump(mode="json"), request)


@router.get("/background-jobs", response_model=BackgroundJobEnvelope[list[BackgroundJob]])
async def list_jobs(request: Request, repository: Repository, user: User) -> Response:
    rows = await repository.list_jobs(owner_user_id=user["id"])
    return success([BackgroundJob.from_row(row).model_dump(mode="json") for row in rows], request)


@router.get(
    "/background-jobs/{id}",
    response_model=BackgroundJobEnvelope[BackgroundJob],
    responses=not_found,
)
async def get_job(id: str, request: Request, repository: Repository, user: User) -> Response:
    return _response(await repository.get(id, owner_user_id=user["id"]), request)


@router.post(
    "/background-jobs/{id}:cancel",
    response_model=BackgroundJobEnvelope[BackgroundJob],
    responses=not_found,
)
async def cancel_job(id: str, request: Request, repository: Repository, user: User) -> Response:
    return _response(await repository.cancel(id, owner_user_id=user["id"]), request)


@router.post(
    "/background-jobs/{id}:retry",
    response_model=BackgroundJobEnvelope[BackgroundJob],
    responses=not_found,
)
async def retry_job(id: str, request: Request, repository: Repository, user: User) -> Response:
    return _response(await repository.retry(id, owner_user_id=user["id"]), request)
