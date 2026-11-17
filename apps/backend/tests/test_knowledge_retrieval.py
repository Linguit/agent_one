import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Event
from typing import NoReturn, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from super_ai.knowledge_retrieval import (
    Chunk,
    KnowledgeRetrieval,
    KnowledgeRetrievalInput,
    RetrievalError,
    bm25l,
    ranked,
    reciprocal,
    tokenize,
)
from super_ai.llm_provider import LlmProvider, RerankHit
from super_ai.memory.sqlite.documents import documents
from super_ai.tenant import OwnerScope
from super_ai.vector_scope import milvus_search_filter

SCOPE = OwnerScope("me", "me")
CORPUS = {
    "a": Chunk("a", "d1", "kb", "source", "连接 ConnectionPool", {}),
    "b": Chunk("b", "d2", "kb", "source", "other", {}),
}


def test_tokenization_and_bm25l() -> None:
    assert set(tokenize("连接池 com.example.Worker trace-987/service")) >= {
        "连",
        "接",
        "池",
        "连接",
        "接池",
        "com.example.worker",
        "trace-987/service",
        "987",
    }
    scores = bm25l("连接", CORPUS)
    assert scores.keys() == {"a"}
    assert scores["a"] > 0
    assert bm25l("other", {"b": CORPUS["b"]})["b"] > 0
    assert bm25l("missing", CORPUS) == {}
    assert list(ranked({"b": reciprocal(1), "a": reciprocal(1)})) == ["a", "b"]
    assert reciprocal(1) + reciprocal(2) == 1 / 61 + 1 / 62


def test_input_and_milvus_scope() -> None:
    assert KnowledgeRetrievalInput(query=" q ").query == "q"
    assert KnowledgeRetrievalInput(query="q").topK == 5
    for payload in ({"query": " "}, {"query": "q", "topK": 6}, {"query": "q", "topK": 0}):
        with pytest.raises(ValidationError):
            KnowledgeRetrievalInput.model_validate(payload)
    assert (
        milvus_search_filter(
            tenant_id="me", allowed_knowledge_base_ids=["kb"], allowed_document_ids=["d"]
        )
        == 'tenantId == "me" and knowledgeBaseId in ["kb"] and documentId in ["d"]'
    )


class Provider:
    def __init__(self, fail: str) -> None:
        self.fail = fail
        self.calls: list[tuple[list[str], int | None]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail == "embedding":
            raise ValueError("secret")
        assert texts == ["连接"]
        return [[0.1] * 1024]

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankHit]:
        if self.fail == "rerank":
            raise ValueError("secret")
        assert query == "连接"
        self.calls.append((documents, top_n))
        return [
            RerankHit(index=i, relevance_score=-0.1 - rank)
            for rank, i in enumerate(reversed(range(len(documents))))
        ][:top_n]


class Retrieval(KnowledgeRetrieval):
    def __init__(self, fail: str = "", *, empty: bool = False) -> None:
        self.stub = Provider(fail)
        self.fail = fail
        self.empty = empty
        self.started = Event()
        self.keyword_started = Event()
        super().__init__(async_sessionmaker(), self.open_provider, self.unused_vectors)

    @asynccontextmanager
    async def open_provider(self) -> AsyncGenerator[LlmProvider]:
        yield cast(LlmProvider, self.stub)

    @staticmethod
    def unused_vectors() -> NoReturn:
        raise AssertionError

    async def corpus(self, scope: OwnerScope, params: KnowledgeRetrievalInput) -> dict[str, Chunk]:
        assert scope == SCOPE
        return CORPUS

    def vector_scores(
        self, scope: OwnerScope, corpus: dict[str, Chunk], embedding: list[float]
    ) -> dict[str, float]:
        self.started.set()
        assert self.keyword_started.wait(2)
        if self.fail == "vector":
            return super().vector_scores(scope, corpus, embedding)
        return {} if self.empty else {"b": 0.8}

    async def keyword_scores(self, query: str, corpus: dict[str, Chunk]) -> dict[str, float]:
        assert await asyncio.to_thread(self.started.wait, 2)
        self.keyword_started.set()
        if self.fail == "keyword":
            corpus = {"bad": cast(Chunk, None)}
        return {} if self.empty else await super().keyword_scores(query, corpus)


async def test_tool_parallel_rerank_and_evidence() -> None:
    retrieval = Retrieval()
    output: object = await retrieval.tool(SCOPE).ainvoke({"query": "连接", "topK": 1})
    assert retrieval.stub.calls == [(["连接 ConnectionPool", "other"], 1)]
    assert output == {
        "results": [
            {
                "chunkId": "b",
                "documentId": "d2",
                "knowledgeBaseId": "kb",
                "source": "source",
                "excerpt": "other",
                "metadata": {},
                "vectorRank": 1,
                "vectorScore": 0.8,
                "bm25Rank": None,
                "bm25Score": None,
                "rrfScore": 1 / 61,
                "rerankRank": 1,
                "rerankScore": -0.1,
                "score": -0.1,
            }
        ]
    }


async def test_empty_recall() -> None:
    assert await Retrieval(empty=True).retrieve(SCOPE, KnowledgeRetrievalInput(query="连接")) == {
        "results": []
    }


@pytest.mark.parametrize(
    ("stage", "message"),
    [
        ("embedding", "Qwen 查询嵌入"),
        ("vector", "Milvus 向量召回"),
        ("keyword", "BM25L 关键词召回"),
        ("rerank", "Qwen 重排"),
    ],
)
async def test_stage_failure(stage: str, message: str) -> None:
    with pytest.raises(RetrievalError, match=message):
        await Retrieval(stage).retrieve(SCOPE, KnowledgeRetrievalInput(query="连接"))


async def test_cross_tenant_no_provider() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(documents.create)
        sessions = async_sessionmaker(engine, class_=AsyncSession)
        # An empty owner-scoped result must short-circuit before creating an external client.
        retrieval = KnowledgeRetrieval(sessions, Retrieval.unused_vectors, Retrieval.unused_vectors)
        async with sessions.begin() as session:
            await session.execute(
                insert(documents).values(
                    id="foreign",
                    owner_user_id="other",
                    knowledge_base_id="kb",
                    filename="foreign.txt",
                    body="连接",
                    index_status="succeeded",
                    mime_type="text/plain",
                    size=1,
                    sha256="hash",
                    uploaded_at=datetime.now(timezone.utc),
                    chunking={},
                )
            )
        assert await retrieval.retrieve(
            SCOPE, KnowledgeRetrievalInput(query="连接", documentId="foreign")
        ) == {"results": []}
    finally:
        await engine.dispose()


async def test_default_top_k_and_twenty_candidate_cap() -> None:
    class ManyChunks(Retrieval):
        async def corpus(
            self, scope: OwnerScope, params: KnowledgeRetrievalInput
        ) -> dict[str, Chunk]:
            return {
                f"{i:02}": Chunk(f"{i:02}", "d1", "kb", "source", f"连接 {i:02}", {})
                for i in range(25)
            }

        def vector_scores(
            self, scope: OwnerScope, corpus: dict[str, Chunk], embedding: list[float]
        ) -> dict[str, float]:
            self.started.set()
            assert self.keyword_started.wait(2)
            return {"19": 0.7}

    retrieval = ManyChunks()
    result = await retrieval.retrieve(SCOPE, KnowledgeRetrievalInput(query="连接"))
    candidates, limit = retrieval.stub.calls[0]
    assert len(candidates) == 20 and candidates[0] == "连接 19"
    assert limit == 5
    results = result["results"]
    assert isinstance(results, list) and len(results) == 5
    hit = results[0]
    assert isinstance(hit, dict) and hit["bm25Score"]
    assert hit["vectorRank"] is None
    assert hit["rrfScore"] == reciprocal(cast(int, hit["bm25Rank"]))
