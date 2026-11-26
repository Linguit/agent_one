from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, JsonValue

from super_ai.contracts import Meta

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_MIME_TYPES = {".md": ("text/markdown", "text/plain"), ".pdf": ("application/pdf",)}
PREVIEW_CHUNKS = 12
PREVIEW_EXCERPT = 400
DEFAULT_MAX_CHARACTERS = 1200
DEFAULT_OVERLAP = 200

Strategy = Literal["fixed-character", "markdown-heading", "paragraph"]
IndexStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class FixedCharacterConfig(BaseModel):
    strategy: Literal["fixed-character"] = "fixed-character"
    maxCharacters: int = Field(default=DEFAULT_MAX_CHARACTERS, gt=0)
    overlap: int = Field(default=DEFAULT_OVERLAP, ge=0)


class NaturalChunkingConfig(BaseModel):
    strategy: Literal["markdown-heading", "paragraph"]


ChunkingConfig = Annotated[
    FixedCharacterConfig | NaturalChunkingConfig, Field(discriminator="strategy")
]


class KnowledgeBase(BaseModel):
    id: str
    name: str


class KnowledgeDocument(BaseModel):
    id: str
    knowledgeBaseId: str
    filename: str
    size: int
    mimeType: Literal["text/markdown", "text/plain", "application/pdf"]
    sha256: str
    uploadedAt: datetime
    indexStatus: IndexStatus
    chunking: ChunkingConfig
    metadata: dict[str, JsonValue] = Field(default_factory=lambda: {})


class ChunkExcerpt(BaseModel):
    index: int
    start: int
    end: int
    excerpt: str = Field(max_length=PREVIEW_EXCERPT)


class ChunkPreview(BaseModel):
    documentId: str
    chunking: ChunkingConfig
    chunks: list[ChunkExcerpt] = Field(max_length=PREVIEW_CHUNKS)


class DocumentDeleted(BaseModel):
    deleted: Literal[True] = True


class DocumentIndexTask(BaseModel):
    id: str
    knowledgeBaseId: str
    documentId: str
    status: IndexStatus
    failureReason: str | None
    retryOfTaskId: str | None
    createdAt: datetime
    updatedAt: datetime
    startedAt: datetime | None
    completedAt: datetime | None


T = TypeVar("T")


class DocumentEnvelope(BaseModel, Generic[T]):
    ok: Literal[True]
    data: T
    meta: Meta
