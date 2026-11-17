import asyncio
import re
from collections import Counter
from collections.abc import Callable, Generator
from contextlib import AbstractAsyncContextManager, contextmanager
from dataclasses import dataclass
from math import isfinite, log
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.document_chunking import chunk_document_text
from super_ai.document_contracts import ChunkingConfig
from super_ai.document_indexing import stable_chunk_id
from super_ai.llm_provider import LlmProvider
from super_ai.memory.sqlite.documents import documents
from super_ai.project_config import JsonObject, JsonValue
from super_ai.tenant import OwnerScope
from super_ai.vector_store import VECTOR_DIMENSION, MilvusVectorStore

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool

_TOKEN = re.compile(r"[\u3400-\u9fff]+|[a-zA-Z0-9_]+(?:[./:$-][a-zA-Z0-9_]+)*")
_CHUNKING = TypeAdapter[ChunkingConfig](ChunkingConfig)
_CANDIDATES = 20


class KnowledgeRetrievalInput(BaseModel):
    """在当前用户的索引语料中检索。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", hide_input_in_errors=True)

    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=5, strict=True)
    knowledgeBaseId: str | None = Field(default=None, min_length=1)
    documentId: str | None = Field(default=None, min_length=1)


@dataclass(frozen=True)
class Chunk:
    chunkId: str
    documentId: str
    knowledgeBaseId: str
    source: str
    excerpt: str
    metadata: JsonObject


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _TOKEN.findall(text):
        if word.isascii():
            word = word.lower()
            tokens.append(word)
            tokens.extend(part for part in re.split(r"[./:$-]", word) if part != word)
        else:
            tokens.extend(word)
            tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


def bm25l(query: str, corpus: dict[str, Chunk]) -> dict[str, float]:
    terms = sorted(set(tokenize(query)))
    counts = {key: Counter(tokenize(chunk.excerpt)) for key, chunk in corpus.items()}
    lengths = {key: sum(words.values()) for key, words in counts.items()}
    average = sum(lengths.values()) / len(lengths) if lengths else 0
    idf = {
        term: log((len(counts) + 1) / (0.5 + sum(term in words for words in counts.values())))
        for term in terms
    }
    scores: dict[str, float] = {}
    for key, words in counts.items():
        score = 0.0
        for term in idf:
            frequency = words[term]
            if frequency:
                normalized = frequency / (0.25 + 0.75 * lengths[key] / average) + 0.5
                score += idf[term] * frequency * 2.5 * normalized / (1.5 + normalized)
        if score > 0:
            scores[key] = score
    return scores


def ranked(scores: dict[str, float]) -> dict[str, tuple[int, float]]:
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return {key: (i, scores[key]) for i, key in enumerate(ordered, 1)}


def reciprocal(rank: int | None) -> float:
    return 0 if rank is None else 1 / (60 + rank)


class RetrievalError(RuntimeError):
    pass


@contextmanager
def retrieval_stage(stage: str) -> Generator[None]:
    try:
        yield
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError(f"知识检索失败（{stage}）") from None


def build_corpus(rows: list[RowMapping]) -> dict[str, Chunk]:
    corpus: dict[str, Chunk] = {}
    for row in rows:
        document = str(row["id"])
        config = _CHUNKING.validate_python(row["chunking"])
        for part in chunk_document_text(cast(str, row["body"]), config):
            key = stable_chunk_id(document, part.index)
            corpus[key] = Chunk(
                key,
                document,
                str(row["knowledge_base_id"]),
                str(row["filename"]),
                part.text,
                {
                    "chunking": cast(JsonObject, config.model_dump(mode="json")),
                    "index": part.index,
                    "start": part.start,
                    "end": part.end,
                },
            )
    return corpus


class KnowledgeRetrieval:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        provider: Callable[[], AbstractAsyncContextManager[LlmProvider]],
        vectors: Callable[[], MilvusVectorStore],
    ) -> None:
        self.sessions = sessions
        self.provider = provider
        self.vectors = vectors

    async def corpus(self, scope: OwnerScope, params: KnowledgeRetrievalInput) -> dict[str, Chunk]:
        query = select(documents).where(
            documents.c.owner_user_id == scope.owner_user_id,
            documents.c.deleted_at.is_(None),
            documents.c.index_status == "succeeded",
        )
        if params.knowledgeBaseId is not None:
            query = query.where(documents.c.knowledge_base_id == params.knowledgeBaseId)
        if params.documentId is not None:
            query = query.where(documents.c.id == params.documentId)
        async with self.sessions() as session:
            rows = list((await session.execute(query)).mappings())
        return await asyncio.to_thread(build_corpus, rows)

    def vector_scores(
        self, scope: OwnerScope, corpus: dict[str, Chunk], embedding: list[float]
    ) -> dict[str, float]:
        with retrieval_stage("Milvus 向量召回"):
            store = self.vectors()
            try:
                store.initialize()
                hits = store.search(
                    scope,
                    sorted({chunk.knowledgeBaseId for chunk in corpus.values()}),
                    embedding,
                    limit=_CANDIDATES,
                    allowed_document_ids=sorted({chunk.documentId for chunk in corpus.values()}),
                )
            finally:
                store.close()
            scores: dict[str, float] = {}
            for hit in hits:
                entity = cast(dict[str, object], hit["entity"])
                key = cast(str, entity["chunkId"])
                chunk = corpus.get(key)
                if chunk is None or (
                    entity["tenantId"],
                    entity["ownerUserId"],
                    entity["knowledgeBaseId"],
                    entity["documentId"],
                ) != (
                    scope.tenant_id,
                    scope.owner_user_id,
                    chunk.knowledgeBaseId,
                    chunk.documentId,
                ):
                    continue
                score = float(cast(float, hit["distance"]))
                if not isfinite(score):
                    raise ValueError("无效向量分数")
                scores[key] = max(score, scores.get(key, score))
            return scores

    async def keyword_scores(self, query: str, corpus: dict[str, Chunk]) -> dict[str, float]:
        with retrieval_stage("BM25L 关键词召回"):
            return await asyncio.to_thread(bm25l, query, corpus)

    async def retrieve(self, scope: OwnerScope, params: KnowledgeRetrievalInput) -> JsonObject:
        with retrieval_stage("BM25L 语料"):
            corpus = await self.corpus(scope, params)
        if not corpus:
            return {"results": []}
        with retrieval_stage("Qwen 提供方"):
            async with self.provider() as provider:
                return await self._search(scope, params, corpus, provider)

    async def _search(
        self,
        scope: OwnerScope,
        params: KnowledgeRetrievalInput,
        corpus: dict[str, Chunk],
        provider: LlmProvider,
    ) -> JsonObject:
        with retrieval_stage("Qwen 查询嵌入"):
            embeddings = await provider.embed([params.query])
            if (
                len(embeddings) != 1
                or len(embeddings[0]) != VECTOR_DIMENSION
                or not all(map(isfinite, embeddings[0]))
            ):
                raise ValueError("无效查询向量")
        vector_scores, keyword_scores = await asyncio.gather(
            asyncio.to_thread(self.vector_scores, scope, corpus, embeddings[0]),
            self.keyword_scores(params.query, corpus),
        )
        vector = ranked(vector_scores)
        keyword = ranked(keyword_scores)
        evidence: dict[str, JsonObject] = {}
        fused: dict[str, float] = {}
        for key in vector.keys() | keyword.keys():
            vr, vs = vector.get(key, (None, None))
            br, bs = keyword.get(key, (None, None))
            fused[key] = reciprocal(vr) + reciprocal(br)
            evidence[key] = {
                "vectorRank": vr,
                "vectorScore": vs,
                "bm25Rank": br,
                "bm25Score": bs,
                "rrfScore": fused[key],
            }
        candidates = list(ranked(fused))[:_CANDIDATES]
        if not candidates:
            return {"results": []}
        with retrieval_stage("Qwen 重排"):
            hits = await provider.rerank(
                params.query, [corpus[key].excerpt for key in candidates], top_n=params.topK
            )
            if len(hits) != min(params.topK, len(candidates)) or len(
                {hit.index for hit in hits if 0 <= hit.index < len(candidates)}
            ) != len(hits):
                raise ValueError("无效重排响应")
            results: list[JsonValue] = []
            for i, hit in enumerate(hits, 1):
                key = candidates[hit.index]
                chunk = corpus[key]
                results.append(
                    {
                        "chunkId": key,
                        "documentId": chunk.documentId,
                        "knowledgeBaseId": chunk.knowledgeBaseId,
                        "source": chunk.source,
                        "excerpt": chunk.excerpt,
                        "metadata": chunk.metadata,
                        **evidence[key],
                        "rerankRank": i,
                        "rerankScore": hit.relevance_score,
                        "score": hit.relevance_score,
                    }
                )
            return {"results": results}

    def tool(self, scope: OwnerScope) -> "StructuredTool":
        from langchain_core.tools import StructuredTool, ToolException

        async def knowledge_retrieval(
            query: str,
            topK: int = 5,
            knowledgeBaseId: str | None = None,
            documentId: str | None = None,
        ) -> JsonObject:
            try:
                return await self.retrieve(
                    scope,
                    KnowledgeRetrievalInput(
                        query=query,
                        topK=topK,
                        knowledgeBaseId=knowledgeBaseId,
                        documentId=documentId,
                    ),
                )

            except RetrievalError as error:
                raise ToolException(str(error)) from None

        return StructuredTool.from_function(
            coroutine=knowledge_retrieval,
            name="knowledge_retrieval",
            description="检索当前用户已索引的知识文档，返回带来源和排序证据的文本片段。",
            args_schema=KnowledgeRetrievalInput,
            handle_tool_error=True,
            handle_validation_error="知识检索参数无效。",
        )
