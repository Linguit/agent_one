from hashlib import sha256
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from sqlalchemy import select, text
from starlette.responses import Response

from super_ai.alert_inputs import redact
from super_ai.chat_api import Owner
from super_ai.chat_contracts import ChatEnvelope
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.diagnostic_case_contracts import DiagnosticCase, SavedDiagnosisKnowledge
from super_ai.diagnostic_case_source import source_metadata, successful_source
from super_ai.diagnostic_runtime import safe_secrets
from super_ai.document_api import default_knowledge_base_id
from super_ai.document_contracts import FixedCharacterConfig
from super_ai.memory.sqlite.diagnostic_cases import DiagnosticCaseRepository
from super_ai.memory.sqlite.diagnostic_schema import tasks
from super_ai.memory.sqlite.documents import DocumentRepository, DuplicateDocument
from super_ai.memory.sqlite.index_tasks import IndexTasks
from super_ai.memory.sqlite.jobs import JobRepository
from super_ai.project_config import JsonObject

router = APIRouter(
    prefix="/aiops",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={code: {"model": FailureEnvelope} for code in (401, 404, 409)},
)


def repository(request: Request) -> DiagnosticCaseRepository:
    return cast(DiagnosticCaseRepository, request.app.state.diagnostic_cases)


Cases = Annotated[DiagnosticCaseRepository, Depends(repository)]


@router.get("/diagnostic-cases", response_model=ChatEnvelope[list[DiagnosticCase]])
async def list_cases(request: Request, scope: Owner, repo: Cases) -> Response:
    return success(
        [case.model_dump(mode="json", by_alias=True) for case in await repo.list_cases(scope)],
        request,
    )


@router.get("/diagnostic-cases/{id}", response_model=ChatEnvelope[DiagnosticCase])
async def get_case(id: str, request: Request, scope: Owner, repo: Cases) -> Response:
    case = await repo.get(scope, id)
    if case is None:
        return failure("BUSINESS_NOT_FOUND", request)
    return success(case.model_dump(mode="json", by_alias=True), request)


@router.post(
    "/diagnostics/{id}:save-to-knowledge", response_model=ChatEnvelope[SavedDiagnosisKnowledge]
)
async def legacy_save_to_knowledge(id: str, request: Request, scope: Owner) -> Response:
    """Legacy explicit content-deduplicated save. No structured case or automatic persistor."""
    jobs = cast(JobRepository, request.app.state.job_repository)
    documents = cast(DocumentRepository, request.app.state.document_repository)
    try:
        async with jobs.factory.begin() as db:
            await db.execute(text("BEGIN IMMEDIATE"))
            exists = await db.scalar(
                select(tasks.c.id).where(
                    tasks.c.owner_user_id == scope.owner_user_id,
                    tasks.c.id == id,
                )
            )
            if exists is None:
                return failure("BUSINESS_NOT_FOUND", request)
            source = await successful_source(db, scope, id)
            if source is None:
                return failure("BUSINESS_CONFLICT", request)
            config = cast(JsonObject, request.app.state.project_config)
            body = cast(str, redact(str(source.report["content"]), safe_secrets(config)))
            kb = default_knowledge_base_id(scope)
            document = await documents.add(
                scope,
                kb,
                filename=f"diagnostic-report-{id}.md",
                size=len(body.encode("utf-8")),
                mime_type="text/markdown",
                sha256=sha256(body.encode("utf-8")).hexdigest(),
                chunking=FixedCharacterConfig(),
                body=body,
                overwrite=False,
                metadata=source_metadata(source, "diagnostic-report"),
                transaction=db,
            )
            index_task = await IndexTasks(jobs).create(
                scope, kb, str(document["id"]), transaction=db
            )
            if index_task is None:
                raise LookupError("报告文档无法调度索引")
            result = SavedDiagnosisKnowledge(
                documentId=str(document["id"]),
                indexTaskId=str(index_task["id"]),
                knowledgeBaseId=kb,
            )
    except DuplicateDocument:
        return failure("BUSINESS_CONFLICT", request)
    return success(result.model_dump(mode="json"), request)
