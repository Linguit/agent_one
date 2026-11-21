import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from super_ai.knowledge_retrieval import KnowledgeRetrieval, KnowledgeRetrievalInput, RetrievalError
from super_ai.llm_provider import create_llm_provider
from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head
from super_ai.memory.sqlite.tool_audits import ToolAuditRepository
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope


async def _authenticate(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    credentials = {"email": email, "password": "chat-test-password"}
    assert (await client.post("/auth/register", json=credentials)).status_code == 200
    login = await client.post("/auth/login", json=credentials)
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['data']['token']}"}


def _error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status
    result = response.json()
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert result["meta"]["requestId"] == response.headers["X-Request-ID"]


def test_chat_openapi() -> None:
    paths = create_app(config={}).openapi()["paths"]
    base = "/chat/sessions"
    for suffix, method in (
        ("", "get"),
        ("", "post"),
        ("/{id}", "get"),
        ("/{id}", "delete"),
        ("/{id}/messages", "post"),
        ("/{id}/messages:clear", "post"),
        ("/{id}/messages:stream", "post"),
        ("/{id}/tool-call-audits", "get"),
    ):
        operation = paths[base + suffix][method]
        assert "401" in operation["responses"]
        assert ("403" in operation["responses"]) == bool(suffix)
        assert operation["security"]


async def test_chat_lifecycle_and_rollback(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'chat.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    app = create_app(
        config={
            "database": {"url": url},
            "llm": {"chatModel": "test"},
            "modelCapabilities": {"test": {"contextWindowTokens": 100000}},
        }
    )
    base = "/chat/sessions"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):
        _error(await client.get(base), 401, "AUTH_UNAUTHORIZED")
        alice = await _authenticate(client, "alice@example.test")
        bob = await _authenticate(client, "bob@example.test")
        first = (await client.post(base, headers=alice, json={})).json()["data"]
        second = (await client.post(base, headers=alice)).json()["data"]
        other = (await client.post(base, headers=bob)).json()["data"]
        assert (await client.get(base, headers=alice)).json()["data"] == [second, first]
        assert (await client.get(base, headers=bob)).json()["data"] == [other]
        detail_path = f"{base}/{first['id']}"
        append_path = detail_path + "/messages"
        clear_path = detail_path + "/messages:clear"
        user_body = {"role": "user", "content": "  " + "你" * 90 + "\n问题"}
        for method, path, body in [
            ("GET", detail_path, None),
            ("DELETE", detail_path, None),
            ("POST", append_path, user_body),
            ("POST", clear_path, None),
            ("GET", base + "/unknown", None),
        ]:
            response = await client.request(method, path, headers=bob, json=body)
            _error(response, 403, "AUTH_FORBIDDEN")

        invalid = await client.post(append_path, headers=alice, json={**user_body, "content": " "})
        _error(invalid, 422, "VALIDATION_INVALID_REQUEST")
        reply = {
            "role": "assistant",
            "content": "回复",
            "metadata": {
                "references": [{"id": "document", "position": {"line": 3}}],
                "toolCallIds": ["call-1"],
                "version": 1,
            },
        }
        added = (await client.post(append_path, headers=alice, json=reply)).json()["data"]
        assert added["session"]["title"] == first["title"]
        assert added["message"]["metadata"] == reply["metadata"]
        replies = await asyncio.gather(
            *[client.post(append_path, headers=alice, json=user_body) for _ in range(5)]
        )
        assert all(item.status_code == 200 for item in replies)
        snapshot = (await client.get(detail_path, headers=alice)).json()["data"]
        assert [item["sequence"] for item in snapshot["messages"]] == list(range(1, 7))
        assert snapshot["session"]["title"] == "你" * 80
        assert snapshot["messages"][0] == added["message"]
        assert snapshot["session"]["updatedAt"] > first["updatedAt"]
        assert (await client.get(base, headers=alice)).json()["data"][0] == snapshot["session"]

        factory = app.state.db_session_factory
        async with factory.begin() as db:
            await db.execute(
                text("""
                CREATE TRIGGER reject_chat_insert BEFORE INSERT ON chat_messages
                WHEN NEW.content = 'rollback'
                BEGIN SELECT RAISE(ABORT, 'test rollback'); END
            """)
            )
        failing = await client.post(
            append_path, headers=alice, json={"role": "user", "content": "rollback"}
        )
        _error(failing, 500, "SYSTEM_INTERNAL_ERROR")
        assert (await client.get(detail_path, headers=alice)).json()["data"] == snapshot

        cleared = (await client.post(clear_path, headers=alice)).json()["data"]
        assert cleared["session"]["id"] == first["id"]
        assert cleared["session"]["title"] == first["title"]
        assert cleared["messages"] == []
        assert (await client.get(detail_path, headers=alice)).json()["data"] == cleared
        again = await client.post(
            append_path, headers=alice, json={"role": "user", "content": "  新的  标题  "}
        )
        assert again.json()["data"]["message"]["sequence"] == 1
        assert again.json()["data"]["session"]["title"] == "新的 标题"

        async with factory.begin() as db:
            await db.execute(text("UPDATE chat_sessions SET updated_at = '2026-01-01 00:00:00'"))
        tied = (await client.get(base, headers=alice)).json()["data"]
        assert [row["id"] for row in tied] == sorted([first["id"], second["id"]], reverse=True)
        assert (await client.delete(detail_path, headers=alice)).json()["data"] == {"deleted": True}
        _error(await client.get(detail_path, headers=alice), 403, "AUTH_FORBIDDEN")
        assert (await client.get(base, headers=bob)).json()["data"][0]["id"] == other["id"]
        async with factory() as db:
            assert (await db.execute(text("SELECT count(*) FROM chat_messages"))).scalar_one() == 0


async def test_agent_chat_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'agent.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    config: JsonObject = {
        "database": {"url": url},
        "llm": {
            "apiKey": "token-sentinel",
            "baseUrl": "https://qwen.test/v1",
            "rerankUrl": "https://qwen.test/rerank",
            "retries": 0,
        },
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1000000}},
    }
    secret_query = "查询参数值 sentinel"
    answer = "你😀e\u0301\n好"
    calls: list[str] = []
    scopes: list[OwnerScope] = []

    async def retrieve(
        self: KnowledgeRetrieval, scope: OwnerScope, params: KnowledgeRetrievalInput
    ) -> JsonObject:
        scopes.append(scope)
        if params.query == "fail":
            raise RetrievalError("工具输出 sentinel")
        assert params.query == secret_query
        return {
            "results": [
                {"source": "资料.md", "knowledgeBaseId": "kb", "documentId": "doc"},
                {"source": "资料.md", "knowledgeBaseId": "kb", "documentId": "doc"},
            ]
        }

    def respond(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = json.loads(request.content)
        assert {item["function"]["name"] for item in payload["tools"]} == {
            "knowledge_retrieval",
            "get_current_time",
            "load_skill",
        }
        last = payload["messages"][-1]
        value = last["content"]
        calls.append(last["role"])
        if value == "模型错误":
            return httpx.Response(500, json={"error": {"message": "token-sentinel"}})
        message: dict[str, object] = {"role": "assistant", "content": answer}
        reason = "stop"
        if last["role"] == "user" and value in ("查一下", "工具错误", "几点了"):
            name = "get_current_time" if value == "几点了" else "knowledge_retrieval"
            arguments = (
                {}
                if name == "get_current_time"
                else {
                    "query": "fail" if value == "工具错误" else secret_query,
                }
            )
            message.update(
                content=None,
                tool_calls=[
                    {
                        "id": "model-call",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            )
            if value == "工具错误":
                cast(list[dict[str, object]], message["tool_calls"]).append(
                    {
                        "id": "parallel-time",
                        "type": "function",
                        "function": {"name": "get_current_time", "arguments": "{}"},
                    }
                )
            if value == "查一下":
                message["reasoning_content"] = "模型返回的推理😀"
            reason = "tool_calls"
        elif last["role"] == "tool" and last["content"].startswith("{"):
            assert json.loads(last["content"])["results"][0]["source"] == "资料.md"
        elif last["role"] == "tool":
            assert datetime.fromisoformat(last["content"]).utcoffset() is not None
        return httpx.Response(
            200,
            json={
                "id": "chat-mock",
                "model": "qwen3.7-max",
                "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            },
        )

    @asynccontextmanager
    async def model() -> AsyncGenerator[BaseChatModel]:
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as upstream,
            create_llm_provider(config, openai_client=upstream) as provider,
        ):
            yield provider.chat_model

    def frames(response: httpx.Response) -> list[dict[str, Any]]:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events: list[dict[str, Any]] = []
        for seq, frame in enumerate(response.text.strip().split("\n\n"), 1):
            wire_id, wire_event, data = frame.splitlines()
            event = json.loads(data.removeprefix("data: "))
            assert event["id"] == wire_id.removeprefix("id: ")
            assert event["id"].endswith(f":{seq}") and event["sequence"] == seq
            assert event["type"] == wire_event.removeprefix("event: ")
            assert event["channel"] == "chat"
            events.append(event)
        assert len({event["id"] for event in events}) == len(events)
        return events

    monkeypatch.setattr(KnowledgeRetrieval, "retrieve", retrieve)
    agent_logger = logging.getLogger("super_ai.agent_chat")
    # Alembic's fileConfig resets logging after pytest installs its root capture handler.
    monkeypatch.setattr(agent_logger, "disabled", False)
    monkeypatch.setattr(agent_logger, "handlers", [caplog.handler])
    monkeypatch.setattr(agent_logger, "propagate", False)
    caplog.set_level(logging.INFO, logger=agent_logger.name)
    app = create_app(config=config, chat_model_factory=model)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        alice = await _authenticate(client, "alice@example.test")
        bob = await _authenticate(client, "bob@example.test")
        owner = (await client.get("/auth/me", headers=alice)).json()["data"]["id"]
        session = (await client.post("/chat/sessions", headers=alice)).json()["data"]["id"]
        path = f"/chat/sessions/{session}"
        stream = path + "/messages:stream"
        audits_path = path + "/tool-call-audits"
        _error(
            await client.post(stream, headers=bob, json={"content": "越权"}),
            403,
            "AUTH_FORBIDDEN",
        )
        _error(await client.get(audits_path, headers=bob), 403, "AUTH_FORBIDDEN")
        assert not calls

        first = frames(
            await client.post(
                stream,
                headers=alice,
                json={"content": "查一下", "metadata": {"source": "test"}},
            )
        )
        assert [item["type"] for item in first] == [
            "reasoning.delta",
            "tool.call",
            "tool.call",
            "reference.source",
            *(["content.delta"] * len(answer)),
            "complete",
        ]
        assert first[0]["data"] == {"text": "模型返回的推理😀"}
        assert [item["data"]["status"] for item in first[1:3]] == ["started", "completed"]
        tool_id = first[1]["data"]["toolId"]
        assert first[2]["data"]["toolId"] == tool_id
        assert [item["data"]["text"] for item in first[4:-1]] == list(answer)
        assert scopes == [OwnerScope(owner, owner)]
        assert calls == ["user", "tool"]

        second = frames(await client.post(stream, headers=alice, json={"content": "你好"}))
        assert [item["type"] for item in second] == [
            *(["content.delta"] * len(answer)),
            "complete",
        ]
        assert calls == ["user", "tool", "user"]
        assert len(scopes) == 1
        rows = (await client.get(path, headers=alice)).json()["data"]["messages"]
        assert rows[0]["metadata"]["source"] == "test"
        assert rows[1]["content"] == answer
        assert rows[1]["id"] == first[-1]["data"]["result"]["messageId"]
        assert rows[1]["metadata"] == {
            "toolCallIds": [tool_id],
            "references": [first[3]["data"]],
        }
        assert rows[3]["metadata"] == {"toolCallIds": [], "references": []}
        assert first[0]["id"].split(":")[0] != second[0]["id"].split(":")[0]

        time_events = frames(await client.post(stream, headers=alice, json={"content": "几点了"}))
        assert [event["data"]["status"] for event in time_events[:2]] == ["started", "completed"]
        assert time_events[0]["data"]["toolName"] == "get_current_time"
        assert time_events[-1]["type"] == "complete"

        calls_before_failure = len(calls)
        failed = frames(await client.post(stream, headers=alice, json={"content": "工具错误"}))
        assert calls[calls_before_failure:] == ["user"]
        assert [item["type"] for item in failed] == ["tool.call"] * 4 + ["error"]
        for tool_name, terminal in (
            ("knowledge_retrieval", "failed"),
            ("get_current_time", "completed"),
        ):
            assert [
                event["data"]["status"]
                for event in failed[:-1]
                if event["data"]["toolName"] == tool_name
            ] == ["started", terminal]
        assert failed[-1]["data"]["error"]["code"] == "SYSTEM_INTERNAL_ERROR"
        provider_failure = frames(
            await client.post(
                stream,
                headers=alice,
                json={"content": "模型错误"},
            )
        )
        assert [item["type"] for item in provider_failure] == ["error"]
        rows = (await client.get(path, headers=alice)).json()["data"]["messages"]
        assert [row["role"] for row in rows] == ["user", "assistant"] * 3 + ["user", "user"]

        audits = (await client.get(audits_path, headers=alice)).json()["data"]
        assert [(audit["toolName"], audit["status"]) for audit in audits[:2]] == [
            ("knowledge_retrieval", "completed"),
            ("get_current_time", "completed"),
        ]
        assert {(audit["toolName"], audit["status"]) for audit in audits[2:]} == {
            ("knowledge_retrieval", "failed"),
            ("get_current_time", "completed"),
        }
        assert audits[0]["arguments"] == {"query": secret_query}
        assert audits[0]["id"] == tool_id and audits[0]["resultSummary"]
        failed_audit = next(audit for audit in audits if audit["status"] == "failed")
        assert failed_audit["errorMessage"] and failed_audit["resultSummary"] is None
        assert all(
            audit["chatSessionId"] == session
            and audit["diagnosticTaskId"] is None
            and audit["ownerUserId"] == owner
            and audit["completedAt"] >= audit["startedAt"]
            and audit["durationMs"] >= 0
            for audit in audits
        )
        repo = cast(ToolAuditRepository, app.state.tool_audits)
        owner_scope = OwnerScope(owner, owner)
        with pytest.raises(IntegrityError):
            await repo.start(
                owner_scope,
                "test",
                {},
                chat_session_id=session,
                diagnostic_task_id="task",
            )
        with pytest.raises(IntegrityError):
            await repo.start(owner_scope, "test", {})
        diagnostic = await repo.start(owner_scope, "test", {}, diagnostic_task_id="task")
        with pytest.raises(LookupError):
            await repo.finish(OwnerScope("other", "other"), diagnostic, 0, result_summary="ok")
        await repo.finish(owner_scope, diagnostic, 0, result_summary="ok")
        assert len(await repo.list_chat(owner_scope, session)) == 4
        await client.delete(path, headers=alice)
        assert not await repo.list_chat(owner_scope, session)
    assert any(getattr(entry, "argumentKeys", []) == ["query"] for entry in caplog.records)
    assert all(
        needle not in repr(record.__dict__)
        for needle in (secret_query, "工具输出 sentinel", "token-sentinel", "查一下")
        for record in caplog.records
        if record.name == "super_ai.agent_chat"
    )
