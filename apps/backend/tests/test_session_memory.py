import json
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from alembic.config import Config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from sqlalchemy import create_engine, inspect, text

from alembic import command
from super_ai import session_memory
from super_ai.contracts import ERROR_CATALOG
from super_ai.llm_provider import create_llm_provider
from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite.chat import ChatRepository
from super_ai.project_config import JsonObject
from super_ai.session_memory import MemoryFailure, SessionMemory
from super_ai.tenant import OwnerScope

BACKEND = Path(__file__).resolve().parents[1]


@dataclass
class Harness:
    client: httpx.AsyncClient
    memory: SessionMemory
    repo: ChatRepository
    auth: dict[str, str]
    bob: dict[str, str]
    owner: OwnerScope
    id: str
    calls: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    fail: bool = False
    output: str = "精简摘要"
    middleware_checks: int = 0

    @property
    def path(self) -> str:
        return f"/chat/sessions/{self.id}"

    async def seed(self, turns: int) -> None:
        for _ in range(turns):
            for role in ("user", "assistant"):
                await self.repo.append(
                    self.owner, self.id, role=role, content="历史" * 200, metadata={}
                )

    async def snapshot(self) -> dict[str, Any]:
        return (await self.client.get(self.path, headers=self.auth)).json()["data"]


@pytest.fixture
async def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Harness]:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'memory.db').as_posix()}"
    upgrade_head(url, BACKEND)
    config: JsonObject = {
        "database": {"url": url},
        "llm": {
            "apiKey": "test",
            "baseUrl": "https://qwen.test/v1",
            "rerankUrl": "https://qwen.test/rerank",
            "retries": 0,
        },
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1000}},
    }
    fixture: Harness

    def estimate(messages: Sequence[BaseMessage]) -> int:
        texts = [item.text for item in messages]
        if texts[0].startswith("请压缩"):
            return 100
        if any("candidate-limit" == item for item in texts):
            return 950
        if "middleware-limit" in texts:
            fixture.middleware_checks += 1
            return 600 if fixture.middleware_checks <= 2 else 950
        if any(item.startswith("历史摘要（") for item in texts):
            return 100 if fixture.output != "无缩减" else 600
        for item in texts:
            if item.startswith("candidate-"):
                return int(item.removeprefix("candidate-"))
        return 600

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        fixture.calls.append(payload)
        if fixture.fail:
            return httpx.Response(503, json={"error": {"message": "不可用"}})
        return httpx.Response(
            200,
            json={
                "id": "mock",
                "model": "qwen3.7-max",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": fixture.output},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    @asynccontextmanager
    async def model() -> AsyncGenerator[BaseChatModel]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            async with create_llm_provider(config, openai_client=client) as provider:
                yield provider.chat_model

    monkeypatch.setattr(session_memory, "estimate_context_tokens", estimate)
    app = create_app(config=config, chat_model_factory=model)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):

        async def authenticate(email: str) -> tuple[dict[str, str], str]:
            body = {"email": email, "password": "memory-test-password"}
            user = (await client.post("/auth/register", json=body)).json()["data"]
            result = (await client.post("/auth/login", json=body)).json()["data"]
            return {"Authorization": f"Bearer {result['token']}"}, user["id"]

        auth, owner = await authenticate("alice@memory.test")
        bob, _ = await authenticate("bob@memory.test")
        # 估算器创建会话前不访问 fixture。
        id = (await client.post("/chat/sessions", headers=auth)).json()["data"]["id"]
        fixture = Harness(
            client,
            cast(SessionMemory, app.state.session_memory),
            cast(ChatRepository, app.state.chat_repository),
            auth,
            bob,
            OwnerScope(owner, owner),
            id,
        )
        yield fixture


@pytest.mark.parametrize(
    ("mode", "turns", "budget", "expected"),
    [
        ("every_30_turns", 29, 690, False),
        ("every_30_turns", 30, 690, True),
        ("context_70_percent", 1, 690, False),
        ("context_70_percent", 1, 700, True),
        ("manual", 30, 700, False),
        ("manual", 1, 949, False),
    ],
)
async def test_trigger_boundaries(
    harness: Harness, mode: str, turns: int, budget: int, expected: bool
) -> None:
    h = harness
    await h.seed(turns)
    before = await h.snapshot()
    response = await h.client.put(h.path + "/memory", headers=h.auth, json={"memoryMode": mode})
    assert response.json()["data"]["memoryMode"] == mode
    response = await h.client.post(
        h.path + "/messages",
        headers=h.auth,
        json={"role": "user", "content": f"candidate-{budget}"},
    )
    assert response.status_code == 200, response.text
    state = response.json()["data"]["session"]
    assert bool(state["compactedMessageCount"]) == expected
    assert bool(h.calls) == expected
    assert state["contextUsagePercent"] == pytest.approx(state["contextTokens"] / 10)
    assert (await h.snapshot())["messages"][:-1] == before["messages"]
    if expected:
        assert state["compactedMessageCount"] == turns * 2
        assert state["lastCompactedAt"] and not state["canCompact"]
        assert before["messages"][0]["id"] in state["memorySummary"]


async def test_manual_boundary_history_and_current_catalog(harness: Harness) -> None:
    h = harness
    await h.seed(2)
    await h.repo.append(h.owner, h.id, role="user", content="未回答", metadata={})
    before = await h.snapshot()
    response = await h.client.post(h.path + "/memory:compact", headers=h.auth)
    assert response.status_code == 200, response.text
    state = response.json()["data"]
    assert state["compactedMessageCount"] == 4 and state["lastCompactedAt"]
    assert (await h.snapshot())["messages"] == before["messages"]
    record, history = await h.repo.detail(h.owner, h.id)
    context = session_memory.context_messages(record, history, "当前 Prompt 与 Skill catalog")
    assert context[0].text == "当前 Prompt 与 Skill catalog"
    assert context[1].text.startswith("历史摘要")
    assert context[-1].text == "未回答" and len(context) == 3
    calls = len(h.calls)
    assert (await h.client.post(h.path + "/memory:compact", headers=h.auth)).status_code == 200
    assert len(h.calls) == calls  # 无完整 turn 时幂等。
    cleared = (await h.client.post(h.path + "/messages:clear", headers=h.auth)).json()["data"]
    assert cleared["session"]["compactedMessageCount"] == 0
    assert cleared["session"]["memorySummary"] == ""
    assert cleared["session"]["lastCompactedAt"] is None


@pytest.mark.parametrize("failure", ["upstream", "empty", "no_reduction"])
async def test_compaction_failure_rolls_back(harness: Harness, failure: str) -> None:
    h = harness
    await h.seed(1)
    before = await h.snapshot()
    h.fail = failure == "upstream"
    h.output = "" if failure == "empty" else ("无缩减" if failure == "no_reduction" else "摘要")
    result = await h.client.post(h.path + "/memory:compact", headers=h.auth)
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "CHAT_MEMORY_COMPACTION_FAILED"
    assert await h.snapshot() == before


async def test_rejection_atomic_and_http_sse_same_error(harness: Harness) -> None:
    h = harness
    await h.seed(1)
    await h.client.put(h.path + "/memory", headers=h.auth, json={"memoryMode": "manual"})
    before = await h.snapshot()
    for suffix, body in [
        ("/messages", {"role": "user", "content": "candidate-limit"}),
        ("/messages:stream", {"content": "candidate-limit"}),
    ]:
        response = await h.client.post(h.path + suffix, headers=h.auth, json=body)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CHAT_CONTEXT_LIMIT_REACHED"
        assert "手动压缩" in response.json()["error"]["message"]
        assert await h.snapshot() == before and not h.calls
    # 建立流后 capability/catalog 预算变化同样使用共享 SSE error。
    stream = await h.client.post(
        h.path + "/messages:stream", headers=h.auth, json={"content": "middleware-limit"}
    )
    assert stream.status_code == 200
    event = json.loads(stream.text.split("data: ")[1])
    category, status, message = ERROR_CATALOG["CHAT_CONTEXT_LIMIT_REACHED"]
    assert event["data"]["error"] == {
        "code": "CHAT_CONTEXT_LIMIT_REACHED",
        "category": category,
        "httpStatus": status,
        "message": message,
    }
    assert not h.calls


async def test_auto_compaction_then_limit_rolls_back(harness: Harness) -> None:
    h = harness
    await h.seed(1)
    await h.client.put(
        h.path + "/memory", headers=h.auth, json={"memoryMode": "context_70_percent"}
    )
    before = await h.snapshot()
    response = await h.client.post(
        h.path + "/messages", headers=h.auth, json={"role": "user", "content": "candidate-limit"}
    )
    assert response.status_code == 409 and h.calls
    assert await h.snapshot() == before


async def test_owner_and_session_isolation(harness: Harness) -> None:
    h = harness
    await h.seed(1)
    other = (await h.client.post("/chat/sessions", headers=h.auth)).json()["data"]
    for method, suffix, body in [
        ("PUT", "/memory", {"memoryMode": "manual"}),
        ("POST", "/memory:compact", None),
    ]:
        result = await h.client.request(method, h.path + suffix, headers=h.bob, json=body)
        assert result.status_code == 403
    assert not h.calls
    await h.client.put(h.path + "/memory", headers=h.auth, json={"memoryMode": "manual"})
    await h.client.post(h.path + "/memory:compact", headers=h.auth)
    assert (await h.client.get(f"/chat/sessions/{other['id']}", headers=h.auth)).json()["data"][
        "session"
    ] == other
    invalid = await h.client.put(h.path + "/memory", headers=h.auth, json={"memoryMode": "wrong"})
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    "capabilities",
    [
        {},
        {"qwen3.7-max": {"contextWindowTokens": 0}},
        {"qwen3.7-max": {"contextWindowTokens": "1000"}},
    ],
)
async def test_capability_error_no_write(harness: Harness, capabilities: Any) -> None:
    h = harness
    before = await h.repo.detail(h.owner, h.id)
    h.memory.config["modelCapabilities"] = capabilities
    result = await h.client.post(
        h.path + "/messages", headers=h.auth, json={"role": "user", "content": "hello"}
    )
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "CHAT_MODEL_CAPABILITY_INVALID"
    assert await h.repo.detail(h.owner, h.id) == before and not h.calls


def test_pure_estimator_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    def count(messages: Sequence[BaseMessage]) -> int:
        assert len(messages) == 1
        return 123

    monkeypatch.setattr(session_memory, "count_tokens_approximately", count)
    assert session_memory.estimate_context_tokens([HumanMessage(content="测试")]) == 123


def test_migration_roundtrip(tmp_path: Path) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0008_user_chat_configuration")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO users VALUES ('owner','old@test','hash',CURRENT_TIMESTAMP)"))
        db.execute(
            text(
                "INSERT INTO chat_sessions "
                "(id,owner_user_id,title,created_at,updated_at,"
                "last_sequence,has_user_message) VALUES "
                "('session','owner','历史',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1,1)"
            )
        )
        db.execute(
            text(
                "INSERT INTO chat_messages "
                "(id,owner_user_id,session_id,role,content,metadata,sequence,created_at) VALUES "
                "('message','owner','session','user','原始内容','{}',1,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as db:
        row = db.execute(
            text(
                "SELECT memory_mode,memory_summary,compacted_message_count,"
                "context_tokens,last_compacted_at FROM chat_sessions"
            )
        ).one()
        assert tuple(row) == ("every_30_turns", "", 0, 0, None)
    command.downgrade(cfg, "0008_user_chat_configuration")
    assert "memory_mode" not in {
        column["name"] for column in inspect(engine).get_columns("chat_sessions")
    }
    command.upgrade(cfg, "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT content FROM chat_messages")) == "原始内容"
    engine.dispose()


def test_missing_capability_is_explicit() -> None:
    memory = object.__new__(SessionMemory)
    memory.config = {}
    with pytest.raises(MemoryFailure, match="CHAT_MODEL_CAPABILITY_INVALID"):
        memory.window()


async def test_stream_uses_summary_and_keeps_full_history(harness: Harness) -> None:
    h = harness
    await h.seed(1)
    await h.client.post(h.path + "/memory:compact", headers=h.auth)
    before = await h.snapshot()
    response = await h.client.post(
        h.path + "/messages:stream", headers=h.auth, json={"content": "新问题"}
    )
    assert "event: complete" in response.text
    model_messages = h.calls[-1]["messages"]
    assert model_messages[1]["content"].startswith("历史摘要")
    assert model_messages[-1]["content"] == "新问题"
    assert "历史" * 200 not in json.dumps(model_messages, ensure_ascii=False)
    assert (await h.snapshot())["messages"][:2] == before["messages"]


async def test_failed_user_does_not_count_or_block_future_turns(harness: Harness) -> None:
    h = harness
    await h.repo.append(h.owner, h.id, role="user", content="失败问题", metadata={})
    await h.seed(29)
    record, history = await h.repo.detail(h.owner, h.id)
    assert session_memory.complete_prefix(history, record.compacted_message_count) == (59, 29)
    await h.seed(1)
    response = await h.client.post(
        h.path + "/messages", headers=h.auth, json={"role": "user", "content": "candidate-690"}
    )
    assert response.json()["data"]["session"]["compactedMessageCount"] == 61


@pytest.mark.parametrize(("mode", "turns"), [("context_70_percent", 1), ("every_30_turns", 30)])
async def test_automatic_failure_has_no_partial_write(
    harness: Harness, mode: str, turns: int
) -> None:
    h = harness
    await h.seed(turns)
    await h.client.put(h.path + "/memory", headers=h.auth, json={"memoryMode": mode})
    before = await h.snapshot()
    h.fail = True
    response = await h.client.post(
        h.path + "/messages:stream", headers=h.auth, json={"content": "candidate-700"}
    )
    assert response.status_code == 502
    assert await h.snapshot() == before


async def test_chunked_summary_calls_stay_below_hard_limit(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness
    await h.seed(2)

    def estimate(messages: Sequence[BaseMessage]) -> int:
        return sum(len(message.text) for message in messages)

    monkeypatch.setattr(session_memory, "estimate_context_tokens", estimate)
    before, messages = await h.repo.detail(h.owner, h.id)
    response = await h.client.post(h.path + "/memory:compact", headers=h.auth)
    assert response.status_code == 200, response.text
    assert len(h.calls) >= 2
    for call in h.calls:
        assert sum(len(message["content"]) for message in call["messages"]) < 950
    after, restored = await h.repo.detail(h.owner, h.id)
    assert restored == messages and after.compacted_message_count == 4
    assert before.compacted_message_count == 0
