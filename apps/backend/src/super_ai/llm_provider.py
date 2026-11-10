"""百炼异步模型边界。客户端只在显式创建时初始化。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict

import httpx
from pydantic import BaseModel, ConfigDict, Field

from super_ai.llm_config import ModelConfig
from super_ai.project_config import JsonObject

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


Capability = Literal["chat", "embedding", "rerank"]
EMBEDDING_MODEL = "text-embedding-v4"
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_BATCH_SIZE = 10
RERANK_MODEL = "qwen3-vl-rerank"


class ProviderError(RuntimeError):
    """调用失败，外部响应与异常已脱敏。"""


class ProviderReadiness(TypedDict):
    provider: str
    model: str
    baseUrl: str
    latency: float  # 毫秒


class RerankHit(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    index: int = Field(ge=0)
    relevance_score: float = Field(allow_inf_nan=False)


class _RerankOutput(BaseModel):
    results: list[RerankHit]


class _RerankResponse(BaseModel):
    output: _RerankOutput


class LlmProvider(Protocol):
    @property
    def context_window_tokens(self) -> int: ...

    async def chat(self, messages: str | list[BaseMessage]) -> BaseMessage: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankHit]: ...

    async def readiness(self, capability: Capability = "chat") -> ProviderReadiness: ...


def _provider_error(operation: str) -> ProviderError:
    # 供应商可能回显请求头和配置。只保留安全的操作名。
    return ProviderError(f"百炼 {operation} 失败，供应商错误详情 [redacted]")


class QwenOpenAIProvider:
    def __init__(
        self,
        config: ModelConfig,
        *,
        sync_client: httpx.Client,
        openai_client: httpx.AsyncClient,
        rerank_client: httpx.AsyncClient,
    ) -> None:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        self._config = config.llm
        profile = config.modelCapabilities[config.llm.chatModel]
        self._context_window_tokens = profile.contextWindowTokens
        self._rerank_client = rerank_client
        try:
            self._chat = ChatOpenAI(
                model=self._config.chatModel,
                api_key=self._config.apiKey,
                base_url=str(self._config.baseUrl),
                temperature=self._config.temperature,
                timeout=self._config.timeout,
                max_retries=self._config.retries,
                organization="",
                openai_proxy="",
                use_responses_api=False,
                http_client=sync_client,
                http_async_client=openai_client,
            )
            self._embedding = OpenAIEmbeddings(
                model=EMBEDDING_MODEL,
                api_key=self._config.apiKey,
                base_url=str(self._config.baseUrl),
                dimensions=EMBEDDING_DIMENSIONS,
                check_embedding_ctx_length=False,
                openai_api_type="openai",
                chunk_size=EMBEDDING_BATCH_SIZE,
                timeout=self._config.timeout,
                max_retries=self._config.retries,
                organization="",
                openai_proxy="",
                model_kwargs={"encoding_format": "float"},
                http_client=sync_client,
                http_async_client=openai_client,
            )
        except Exception:
            pass
        else:
            return
        raise _provider_error("客户端初始化") from None

    @property
    def context_window_tokens(self) -> int:
        return self._context_window_tokens

    async def chat(self, messages: str | list[BaseMessage]) -> BaseMessage:
        return await self._invoke_chat(messages)

    async def _invoke_chat(
        self, messages: str | list[BaseMessage], *, probe: bool = False
    ) -> BaseMessage:
        try:
            if probe:
                return await self._chat.ainvoke(
                    messages, max_tokens=1, extra_body={"enable_thinking": False}
                )
            return await self._chat.ainvoke(messages)
        except Exception:
            pass
        raise _provider_error("对话探测" if probe else "对话") from None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 关闭上下文长度检查后，OpenAIEmbeddings 以原始字符串顺序分批。
        try:
            vectors = await self._embedding.aembed_documents(texts)
            if len(vectors) != len(texts) or any(
                len(vector) != EMBEDDING_DIMENSIONS for vector in vectors
            ):
                raise ValueError("嵌入响应形状无效")
            return vectors
        except Exception:
            pass
        raise _provider_error("嵌入") from None

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[RerankHit]:
        if top_n is not None and top_n < 1:
            raise ValueError("top_n 必须为正整数")
        if not documents:
            return []
        expected = len(documents) if top_n is None else min(top_n, len(documents))
        payload: dict[str, object] = {
            "model": RERANK_MODEL,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": expected, "return_documents": False},
        }
        try:
            response = await self._post_rerank(payload)
            hits = _RerankResponse.model_validate_json(response.content).output.results
            indices = {hit.index for hit in hits}
            if len(hits) != expected or len(indices) != expected or max(indices) >= len(documents):
                raise ValueError("重排响应索引无效")
            return hits
        except Exception:
            pass
        raise _provider_error("重排") from None

    async def _post_rerank(self, payload: dict[str, object]) -> httpx.Response:
        for attempt in range(self._config.retries + 1):
            try:
                response = await self._rerank_client.post(
                    str(self._config.rerankUrl),
                    json=payload,
                    headers={"Authorization": f"Bearer {self._config.apiKey.get_secret_value()}"},
                    timeout=self._config.timeout,
                    follow_redirects=False,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if attempt == self._config.retries or (status not in (408, 429) and status < 500):
                    raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self._config.retries:
                    raise
            else:
                return response
            await asyncio.sleep(min(0.25 * 2 ** min(attempt, 4), 4))
        raise AssertionError("重试次数无效")

    async def readiness(self, capability: Capability = "chat") -> ProviderReadiness:
        start = perf_counter()
        base_url = str(self._config.baseUrl)
        if capability == "chat":
            model = self._config.chatModel
            await self._invoke_chat("Hi", probe=True)
        elif capability == "embedding":
            model = EMBEDDING_MODEL
            await self.embed(["Hi"])
        else:
            model = RERANK_MODEL
            base_url = str(self._config.rerankUrl)
            await self.rerank("Hi", ["Hi"], top_n=1)
        return {
            "provider": self._config.provider,
            "model": model,
            "baseUrl": base_url,
            "latency": (perf_counter() - start) * 1000,
        }


@asynccontextmanager
async def create_llm_provider(
    config: JsonObject,
    *,
    openai_client: httpx.AsyncClient | None = None,
    rerank_client: httpx.AsyncClient | None = None,
) -> AsyncGenerator[LlmProvider, None]:
    """从合并后的配置创建提供者，并在退出时关闭工厂自建的客户端。"""
    settings = ModelConfig.from_project(config)
    async with AsyncExitStack() as stack:
        sync_client = stack.enter_context(httpx.Client(trust_env=False))
        if openai_client is None:
            openai_client = await stack.enter_async_context(httpx.AsyncClient(trust_env=False))
        if rerank_client is None:
            rerank_client = await stack.enter_async_context(httpx.AsyncClient(trust_env=False))
        yield QwenOpenAIProvider(
            settings,
            sync_client=sync_client,
            openai_client=openai_client,
            rerank_client=rerank_client,
        )
