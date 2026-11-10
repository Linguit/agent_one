import json
import traceback
from pathlib import Path
from typing import cast

import httpx
import pytest

from super_ai.llm_config import ModelConfig
from super_ai.llm_provider import Capability, ProviderError, create_llm_provider
from super_ai.project_config import ConfigError, JsonObject, load_project_config

FAKE_KEY = "fake-test-credential"
BASE_URL = "https://openai.test/compatible-mode/v1"
RERANK_URL = "https://rerank.test/native"


@pytest.fixture
def config() -> JsonObject:
    return {
        "llm": {"apiKey": FAKE_KEY, "baseUrl": BASE_URL, "rerankUrl": RERANK_URL},
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1_000_000}},
    }


def test_model_config_uses_merged_json(config: JsonObject, tmp_path: Path) -> None:
    (tmp_path / "project.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "user.project.json").write_text(
        '{"llm":{"apiKey":"local-test-override","temperature":0.5}}', encoding="utf-8"
    )
    settings = ModelConfig.from_project(load_project_config(tmp_path))
    assert settings.llm.apiKey.get_secret_value() == "local-test-override"
    assert str(settings.llm.baseUrl) == BASE_URL
    assert settings.llm.temperature == 0.5
    assert settings.llm.timeout == 120
    assert settings.llm.retries == 2


@pytest.mark.parametrize("field", ["apiKey", "baseUrl", "rerankUrl"])
def test_missing_model_field(config: JsonObject, field: str) -> None:
    llm = config["llm"]
    assert isinstance(llm, dict)
    del llm[field]
    with pytest.raises(ConfigError, match=rf"llm\.{field}") as error:
        ModelConfig.from_project(config)
    assert error.value.__context__ is None
    assert FAKE_KEY not in "".join(traceback.format_exception(error.value))


def test_missing_profile(config: JsonObject) -> None:
    config["modelCapabilities"] = {}
    with pytest.raises(ConfigError, match="contextWindowTokens"):
        ModelConfig.from_project(config)


async def test_model_requests_and_readiness(
    config: JsonObject, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://ignored.test")
    monkeypatch.setenv("OPENAI_PROXY", "https://ignored.test")
    monkeypatch.setenv("OPENAI_API_TYPE", "azure")
    batches: list[list[str]] = []
    chats: list[dict[str, object]] = []
    reranks: list[dict[str, object]] = []
    texts = [f" {index}\n" for index in range(23)]

    def openai_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
        assert request.url.host == "openai.test"
        assert request.extensions["timeout"]["read"] == 120
        payload: dict[str, object] = json.loads(request.content)
        if request.url.path.endswith("/chat/completions"):
            chats.append(payload)
            return httpx.Response(200, json={
                "id": "test-chat", "model": "qwen3.7-max",
                "choices": [{
                    "index": 0, "message": {"role": "assistant", "content": "OK"},
                    "finish_reason": "stop",
                }],
            })
        assert request.url.path.endswith("/embeddings")
        assert payload["model"] == "text-embedding-v4"
        assert payload["dimensions"] == 1024
        assert payload["encoding_format"] == "float"
        batch = cast(list[str], payload["input"])
        batches.append(batch)
        return httpx.Response(200, json={"data": [
            {"index": index, "embedding": [float(texts.index(text)) if text in texts else 0.0]
             * 1024}
            for index, text in enumerate(batch)
        ]})

    def rerank_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == RERANK_URL
        assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
        assert request.extensions["timeout"]["read"] == 120
        reranks.append(json.loads(request.content))
        return httpx.Response(200, json={"output": {"results": [
            {"index": 1 if len(reranks) == 1 else 0, "relevance_score": 0.75},
        ]}})

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(openai_handler)) as openai_client,
        httpx.AsyncClient(transport=httpx.MockTransport(rerank_handler)) as rerank_client,
    ):
        async with create_llm_provider(
            config, openai_client=openai_client, rerank_client=rerank_client
        ) as provider:
            assert provider.context_window_tokens == 1_000_000
            assert (await provider.chat("test")).content == "OK"
            assert await provider.embed([]) == []
            vectors = await provider.embed(texts)
            assert [vector[0] for vector in vectors] == list(range(len(texts)))
            hits = await provider.rerank("query", ["first", "second"], top_n=1)
            assert [(hit.index, hit.relevance_score) for hit in hits] == [(1, 0.75)]
            probes: list[tuple[Capability, str, str]] = [
                ("chat", "qwen3.7-max", BASE_URL),
                ("embedding", "text-embedding-v4", BASE_URL),
                ("rerank", "qwen3-vl-rerank", RERANK_URL),
            ]
            for capability, model, url in probes:
                result = await provider.readiness(capability)
                assert result["provider"] == "qwen"
                assert result["model"] == model and result["baseUrl"] == url
                assert result["latency"] >= 0
        assert not openai_client.is_closed and not rerank_client.is_closed

    assert batches == [texts[:10], texts[10:20], texts[20:], ["Hi"]]
    assert chats[0]["model"] == "qwen3.7-max"
    assert chats[0]["temperature"] == 0.2
    assert chats[1]["max_completion_tokens"] == 1
    assert chats[1]["enable_thinking"] is False
    assert reranks == [
        {
            "model": "qwen3-vl-rerank", "input": {"query": query, "documents": documents},
            "parameters": {"top_n": 1, "return_documents": False},
        }
        for query, documents in [("query", ["first", "second"]), ("Hi", ["Hi"])]
    ]


@pytest.mark.parametrize(("status", "attempts"), [(401, 1), (429, 3), (503, 3), (None, 3)])
async def test_rerank_retry_and_redacted_readiness(
    config: JsonObject, status: int | None, attempts: int
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if status is None:
            raise httpx.ReadTimeout(FAKE_KEY, request=request)
        return httpx.Response(status, json={"message": FAKE_KEY})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        async with create_llm_provider(config, rerank_client=client) as provider:
            with pytest.raises(ProviderError, match=r"\[redacted\]") as error:
                await provider.readiness("rerank")
    assert calls == attempts
    assert error.value.__context__ is None
    assert FAKE_KEY not in "".join(traceback.format_exception(error.value))


async def test_openai_retry_and_redacted_readiness(config: JsonObject) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            429, headers={"retry-after-ms": "1"}, json={"error": {"message": FAKE_KEY}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        async with create_llm_provider(config, openai_client=client) as provider:
            with pytest.raises(ProviderError, match=r"\[redacted\]") as error:
                await provider.readiness()
    assert calls == 3
    assert error.value.__context__ is None
    assert FAKE_KEY not in "".join(traceback.format_exception(error.value))
