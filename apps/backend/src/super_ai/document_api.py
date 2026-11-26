from datetime import timezone
from hashlib import sha256
from itertools import islice
from typing import Annotated, cast
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.security import HTTPBearer
from sqlalchemy.engine import RowMapping
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from super_ai.auth import current_user
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.document_chunking import chunk_document_text, extract_document_text, resolve_chunking
from super_ai.document_contracts import (
    MAX_UPLOAD_BYTES,
    PREVIEW_CHUNKS,
    PREVIEW_EXCERPT,
    UPLOAD_MIME_TYPES,
    ChunkExcerpt,
    ChunkPreview,
    DocumentDeleted,
    DocumentEnvelope,
    KnowledgeBase,
    KnowledgeDocument,
    Strategy,
)
from super_ai.memory.sqlite.documents import DocumentRepository, DuplicateDocument
from super_ai.tenant import OwnerScope


def _owner(user: Annotated[dict[str, str], Depends(current_user)]) -> OwnerScope:
    return OwnerScope(user["id"], user["id"])


def _repository(request: Request) -> DocumentRepository:
    return cast(DocumentRepository, request.app.state.document_repository)


def default_knowledge_base_id(scope: OwnerScope) -> str:
    return str(uuid5(NAMESPACE_URL, f"super-ai:knowledge-base:default:{scope.owner_user_id}"))


def _document(row: RowMapping) -> KnowledgeDocument:
    return KnowledgeDocument.model_validate(
        {
            "id": row["id"],
            "knowledgeBaseId": row["knowledge_base_id"],
            "filename": row["filename"],
            "size": row["size"],
            "mimeType": row["mime_type"],
            "sha256": row["sha256"],
            "uploadedAt": row["uploaded_at"].replace(tzinfo=timezone.utc),
            "indexStatus": row["index_status"],
            "chunking": row["chunking"],
            "metadata": row.get("metadata", {}),
        }
    )


Owner = Annotated[OwnerScope, Depends(_owner)]
Repository = Annotated[DocumentRepository, Depends(_repository)]

router = APIRouter(
    prefix="/knowledge-bases",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={401: {"model": FailureEnvelope}, 500: {"model": FailureEnvelope}},
)
FORBIDDEN: dict[int | str, dict[str, object]] = {403: {"model": FailureEnvelope}}
DOCUMENT_ERRORS: dict[int | str, dict[str, object]] = {**FORBIDDEN, 404: {"model": FailureEnvelope}}


@router.get("", response_model=DocumentEnvelope[list[KnowledgeBase]])
async def list_knowledge_bases(request: Request, scope: Owner) -> Response:
    kb = KnowledgeBase(id=default_knowledge_base_id(scope), name="默认知识库")
    return success([kb.model_dump(mode="json")], request)


@router.get(
    "/{kb}/documents",
    response_model=DocumentEnvelope[list[KnowledgeDocument]],
    responses=FORBIDDEN,
)
async def list_documents(kb: str, request: Request, scope: Owner, repo: Repository) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    rows = await repo.list(scope, kb)
    return success([_document(row).model_dump(mode="json") for row in rows], request)


@router.post(
    "/{kb}/documents",
    response_model=DocumentEnvelope[KnowledgeDocument],
    responses={
        **FORBIDDEN,
        409: {"model": FailureEnvelope, "description": "摘要重复，且未明确覆盖"},
        422: {"model": FailureEnvelope},
    },
    openapi_extra={
        "x-upload-policy": {"maxBytes": MAX_UPLOAD_BYTES, "mimeTypes": UPLOAD_MIME_TYPES},
    },
)
async def upload_document(
    kb: str,
    request: Request,
    scope: Owner,
    repo: Repository,
    file: Annotated[UploadFile, File(description="UTF-8 Markdown 或 PDF")],
    strategy: Annotated[Strategy, Form()] = "fixed-character",
    maxCharacters: Annotated[int | None, Form(gt=0, description="仅 fixed-character")] = None,
    overlap: Annotated[int | None, Form(ge=0, description="仅 fixed-character")] = None,
    overwrite: Annotated[bool, Form(description="允许覆盖同摘要的活跃文档")] = False,
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    mime = (file.content_type or "").split(";", 1)[0].strip().lower()
    try:
        config = resolve_chunking(strategy, maxCharacters, overlap)
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        body = await run_in_threadpool(extract_document_text, filename, mime, content)
    except UnicodeDecodeError:
        return failure("VALIDATION_INVALID_REQUEST", request, details={"message": "需要 UTF-8"})
    except ValueError as exc:
        return failure("VALIDATION_INVALID_REQUEST", request, details={"message": str(exc)})
    try:
        row = await repo.add(
            scope,
            kb,
            filename=filename,
            size=len(content),
            mime_type=mime,
            sha256=sha256(content).hexdigest(),
            chunking=config,
            body=body,
            overwrite=overwrite,
        )
    except DuplicateDocument:
        return failure("BUSINESS_CONFLICT", request)
    return success(_document(row).model_dump(mode="json"), request)


@router.get(
    "/{kb}/documents/{document}",
    response_model=DocumentEnvelope[KnowledgeDocument],
    responses=DOCUMENT_ERRORS,
)
async def get_document(
    kb: str, document: str, request: Request, scope: Owner, repo: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    row = await repo.get(scope, kb, document)
    if row is None:
        return failure("BUSINESS_NOT_FOUND", request)
    return success(_document(row).model_dump(mode="json"), request)


@router.delete(
    "/{kb}/documents/{document}",
    response_model=DocumentEnvelope[DocumentDeleted],
    responses=DOCUMENT_ERRORS,
)
async def delete_document(
    kb: str, document: str, request: Request, scope: Owner, repo: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    if not await repo.delete(scope, kb, document):
        return failure("BUSINESS_NOT_FOUND", request)
    return success(DocumentDeleted().model_dump(mode="json"), request)


@router.get(
    "/{kb}/documents/{document}/chunk-preview",
    response_model=DocumentEnvelope[ChunkPreview],
    responses=DOCUMENT_ERRORS,
)
async def preview_document(
    kb: str, document: str, request: Request, scope: Owner, repo: Repository
) -> Response:
    if kb != default_knowledge_base_id(scope):
        return failure("AUTH_FORBIDDEN", request)
    row = await repo.get(scope, kb, document)
    if row is None:
        return failure("BUSINESS_NOT_FOUND", request)
    config = _document(row).chunking
    chunks = [
        ChunkExcerpt(
            index=chunk.index,
            start=chunk.start,
            end=chunk.end,
            excerpt=chunk.text[:PREVIEW_EXCERPT],
        )
        for chunk in islice(chunk_document_text(cast(str, row["body"]), config), PREVIEW_CHUNKS)
    ]
    preview = ChunkPreview(documentId=document, chunking=config, chunks=chunks)
    return success(preview.model_dump(mode="json"), request)
