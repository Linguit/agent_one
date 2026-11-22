import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import ValidationError

from super_ai.llm_provider import create_llm_provider
from super_ai.main import create_app
from super_ai.mcp_contracts import ConnectionInput
from super_ai.mcp_logging import private_transport_logs
from super_ai.mcp_provider import McpFailure, McpProvider, bounded_tool, discover_real
from super_ai.memory.migrations import upgrade_head
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope


async def test_real_adapter_protocol_with_fake_http_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real MCP SDK initialization/list/call; not official CLS acceptance."""
    methods: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = json.loads(request.content)
        method = payload["method"]
        methods.append(method)
        if "id" not in payload:
            return httpx.Response(202)
        result: dict[str, Any]
        if method == "initialize":
            result = {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "unit-test-server", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "protocol_search",
                        "description": "协议测试",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    }
                ]
            }
        else:
            assert method == "tools/call"
            assert payload["params"]["arguments"] == {"query": "actual argument"}
            result = {
                "content": [{"type": "text", "text": "actual protocol result"}],
                "isError": False,
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(respond), headers=headers, timeout=timeout, auth=auth
        )

    def client(connections: Any) -> MultiServerMCPClient:
        connections["server"]["httpx_client_factory"] = factory
        return MultiServerMCPClient(connections)

    monkeypatch.setattr("langchain_mcp_adapters.client.MultiServerMCPClient", client)
    tools = await discover_real(ConnectionInput.model_validate(body(transport="streamable_http")))
    assert [item.name for item in tools] == ["protocol_search"]
    result = await bounded_tool(tools[0], 2).ainvoke({"query": "actual argument"})
    assert "actual protocol result" in str(result)
    assert methods.count("tools/call") == 1
    # SDK may refresh tool metadata when opening a new invocation session.
    assert methods.count("tools/list") >= 1


def test_sdk_log_privacy_is_context_scoped(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("mcp.client.streamable_http")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    monkeypatch.setattr(logger, "propagate", False)
    logger.setLevel(logging.DEBUG)
    with private_transport_logs():
        logger.warning("Raw result: result-secret")
        logger.debug("Sending arguments: argument-secret")
        try:
            raise ValueError("exception-secret")
        except ValueError:
            logger.exception("SDK exception")
    logger.info("outside-operation")
    assert "secret" not in caplog.text
    assert "outside-operation" in caplog.text


def body(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "真实测试连接",
        "transport": "sse",
        "url": "http://localhost:9000/sse",
        "timeoutSeconds": 1,
        "retries": 1,
        "enabled": True,
        **overrides,
    }


async def auth(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    credentials = {"email": email, "password": "test-password-12345"}
    assert (await client.post("/auth/register", json=credentials)).status_code == 200
    response = await client.post("/auth/login", json=credentials)
    return {"Authorization": "Bearer " + response.json()["data"]["token"]}


def tool(name: str = "cls_search") -> BaseTool:
    async def invoke(query: str) -> str:
        return "result-secret-" + query

    return StructuredTool.from_function(coroutine=invoke, name=name, description="查询工具")


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "file:///etc/passwd"},
        {"url": "http:///missing"},
        {"url": "https://user:password@host/path"},
        {"url": "https://@host/path"},
        {"url": "http://host:invalid/path"},
        {"url": "http://host/\nsecret"},
        {"timeoutSeconds": 0},
        {"timeoutSeconds": 301},
        {"timeoutSeconds": True},
        {"retries": -1},
        {"retries": 6},
        {"retries": 1.5},
        {"name": "  "},
        {"transport": "stdio"},
        {"owner": "intruder"},
        {"headers": {"Authorization": "secret"}},
    ],
)
def test_validation(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConnectionInput.model_validate(body(**changes))


@pytest.mark.parametrize(
    "url", ["http://localhost/sse?a=1", "https://example.test/mcp", "http://[::1]:80/mcp"]
)
def test_url_preserved(url: str) -> None:
    assert ConnectionInput.model_validate(body(url=url)).url == url


async def test_crud_owner_discovery_and_stale_check(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'mcp.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    discovered: list[str] = []
    failure = False

    async def discover(connection: ConnectionInput) -> list[BaseTool]:
        discovered.append(connection.url)
        if failure:
            raise RuntimeError("secret-query-and-result")
        return [tool()]

    app = create_app(config={"database": {"url": url}}, mcp_discover=discover)
    base = "/mcp/connections"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get(base)).status_code == 401
        alice, bob = await auth(client, "alice@mcp.test"), await auth(client, "bob@mcp.test")
        owner = (await client.get("/auth/me", headers=alice)).json()["data"]["id"]
        scope = OwnerScope(owner, owner)
        created = await client.post(base, headers=alice, json=body())
        assert created.status_code == 200
        row = created.json()["data"]
        assert row["owner"] == owner and row["lastCheck"] is None
        path = base + "/" + row["id"]
        assert (await client.get(base, headers=bob)).json()["data"] == []
        for method, route, payload in [
            ("PUT", path, body()),
            ("DELETE", path, None),
            ("POST", path + ":check", None),
        ]:
            assert (
                await client.request(method, route, headers=bob, json=payload)
            ).status_code == 403
        assert not discovered
        checked = (await client.post(path + ":check", headers=alice)).json()["data"]
        assert checked["lastCheck"] and checked["lastError"] is None
        assert checked["discoveredTools"][0]["name"] == "cls_search"
        assert checked["discoveredTools"][0]["inputSchema"]["properties"]["query"]
        provider = cast(McpProvider, app.state.mcp_provider)
        sources = await provider.tools(scope)
        assert sources[0].name == "cls_search" and len(discovered) == 2
        changed = (await client.put(path, headers=alice, json=body(enabled=False))).json()["data"]
        assert changed["lastCheck"] is None and changed["discoveredTools"] == []
        assert await provider.tools(scope) == [] and len(discovered) == 2
        # A late check cannot overwrite the state after an edit.
        record = await provider.repository.get(scope, row["id"])
        await provider.repository.save(
            scope, ConnectionInput.model_validate(body(name="新名称")), row["id"]
        )
        stale = await provider.repository.checked(scope, record, [], "OLD_ERROR")
        assert stale.lastCheck is None and stale.name == "新名称"
        failure = True
        failed = (await client.post(path + ":check", headers=alice)).json()["data"]
        assert failed["lastError"] == "MCP_DISCOVERY_FAILED"
        assert failed["discoveredTools"] == [] and len(discovered) == 4
        assert "secret-query-and-result" not in json.dumps(failed)
        invalid = await client.post(base, headers=alice, json=body(url="http://user:secret@host"))
        assert invalid.status_code == 422 and "secret" not in invalid.text
        assert (await client.delete(path, headers=alice)).json()["data"] == {"deleted": True}
        assert (await client.get(base, headers=alice)).json()["data"] == []


async def test_retry_timeout_cancel_call_once_and_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    async def flaky(connection: ConnectionInput) -> list[BaseTool]:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("secret")
        return [tool()]

    # Repository is unused for isolated discovery tests.
    from super_ai.memory.sqlite.mcp import McpRepository

    provider = McpProvider(cast(McpRepository, None), {}, flaky)
    assert len(await provider.discover(ConnectionInput.model_validate(body()))) == 1
    assert attempts == 2

    async def slow(connection: ConnectionInput) -> list[BaseTool]:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(10)
        return []

    attempts = 0
    provider = McpProvider(cast(McpRepository, None), {}, slow)
    with pytest.raises(McpFailure, match="MCP_TIMEOUT"):
        await provider.discover(ConnectionInput.model_validate(body(retries=0)))
    assert attempts == 1
    task = asyncio.create_task(provider.discover(ConnectionInput.model_validate(body())))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    calls = 0

    async def failing(query: str) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("result-secret")

    wrapped = bounded_tool(StructuredTool.from_function(coroutine=failing, description="test"), 1)
    with pytest.raises(McpFailure, match="MCP_CALL_FAILED"):
        await wrapped.ainvoke({"query": "argument-secret"})
    assert calls == 1

    async def slow_call(query: str) -> str:
        await asyncio.sleep(10)
        return query

    wrapped = bounded_tool(StructuredTool.from_function(coroutine=slow_call, description="test"), 1)
    with pytest.raises(McpFailure, match="MCP_TIMEOUT"):
        await wrapped.ainvoke({"query": "secret"})

    seen: list[str] = []

    async def get_tools(self: MultiServerMCPClient, **kwargs: Any) -> list[BaseTool]:
        seen.append(self.connections["server"]["transport"])
        return [tool()]

    monkeypatch.setattr(MultiServerMCPClient, "get_tools", get_tools)
    for transport in ("sse", "streamable_http"):
        assert (
            len(await discover_real(ConnectionInput.model_validate(body(transport=transport)))) == 1
        )
    assert seen == ["sse", "streamable_http"]


async def test_conflict_disabled_and_fallback(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'scope.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    seen: list[str] = []
    name = "same_tool"

    async def discover(connection: ConnectionInput) -> list[BaseTool]:
        seen.append(connection.url)
        return [tool(name)]

    app = create_app(
        config={"database": {"url": url}, "clsMcpServer": {"url": "http://localhost/sse"}},
        mcp_discover=discover,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        headers = await auth(client, "scope@mcp.test")
        owner = (await client.get("/auth/me", headers=headers)).json()["data"]["id"]
        scope = OwnerScope(owner, owner)
        provider = cast(McpProvider, app.state.mcp_provider)
        assert len(await provider.tools(scope)) == 1 and seen == ["http://localhost/sse"]
        await client.post("/mcp/connections", headers=headers, json=body(enabled=False))
        assert await provider.tools(scope) == [] and len(seen) == 1
        await client.post(
            "/mcp/connections", headers=headers, json=body(url="http://localhost/enabled")
        )
        await client.post(
            "/mcp/connections", headers=headers, json=body(url="http://localhost/other")
        )
        with pytest.raises(McpFailure, match="MCP_TOOL_NAME_CONFLICT"):
            await provider.tools(scope)
        name = "get_current_time"
        with pytest.raises(McpFailure, match="MCP_TOOL_NAME_CONFLICT"):
            await provider.tools(scope)


async def test_chat_injection_audit_and_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'chat.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    config: JsonObject = {
        "database": {"url": url},
        "llm": {
            "provider": "qwen",
            "apiKey": "test",
            "baseUrl": "http://model.test/v1",
            "rerankUrl": "http://model.test/rerank",
            "chatModel": "test",
            "temperature": 0.2,
            "timeout": 5,
            "retries": 0,
        },
        "modelCapabilities": {"test": {"contextWindowTokens": 100000}},
    }
    calls = 0
    fail = False

    async def invoke(query: str) -> str:
        nonlocal calls
        calls += 1
        assert query == "argument-secret"
        if fail:
            raise RuntimeError("exception-secret")
        return "result-secret"

    async def discover(connection: ConnectionInput) -> list[BaseTool]:
        return [
            StructuredTool.from_function(coroutine=invoke, name="cls_search", description="查询")
        ]

    def respond(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = json.loads(request.content)
        assert "cls_search" in {item["function"]["name"] for item in payload["tools"]}
        if payload["messages"][-1]["role"] == "user":
            message: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "mcp-call",
                        "type": "function",
                        "function": {
                            "name": "cls_search",
                            "arguments": json.dumps({"query": "argument-secret"}),
                        },
                    }
                ],
            }
            reason = "tool_calls"
        else:
            assert payload["messages"][-1]["content"] == "result-secret"
            message = {"role": "assistant", "content": "执行完成"}
            reason = "stop"
        return httpx.Response(
            200,
            json={
                "id": "test",
                "model": "test",
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

    app = create_app(config=config, chat_model_factory=model, mcp_discover=discover)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        headers = await auth(client, "chat@mcp.test")
        await client.post("/mcp/connections", headers=headers, json=body(retries=5))
        session = (await client.post("/chat/sessions", headers=headers)).json()["data"]["id"]
        path = f"/chat/sessions/{session}"
        for failure in (False, True):
            fail = failure
            stream = await client.post(
                path + "/messages:stream", headers=headers, json={"content": "执行查询"}
            )
            events = [
                json.loads(line[6:])
                for line in stream.text.splitlines()
                if line.startswith("data: ")
            ]
            statuses = [event["data"]["status"] for event in events if event["type"] == "tool.call"]
            assert statuses == ["started", "failed" if fail else "completed"]
            assert events[-1]["type"] == ("error" if fail else "complete")
            if fail:
                assert events[-1]["data"]["error"]["code"] == "MCP_CALL_FAILED"
        assert calls == 2  # retries=5 never retries a tool invocation
        audits = (await client.get(path + "/tool-call-audits", headers=headers)).json()["data"]
        assert len(audits) == 2
        assert all(row["arguments"] == {"query": "[REDACTED]"} for row in audits)
        assert all(row["durationMs"] >= 0 for row in audits)
        for secret in ("argument-secret", "result-secret", "exception-secret"):
            assert secret not in json.dumps(audits) and secret not in caplog.text
        await client.post(
            "/mcp/connections",
            headers=headers,
            json=body(name="同名工具来源", url="http://localhost/second"),
        )
        conflict = await client.post(
            path + "/messages:stream", headers=headers, json={"content": "冲突时不得调用"}
        )
        assert '"code": "MCP_TOOL_NAME_CONFLICT"' in conflict.text
        assert "event: tool.call" not in conflict.text and calls == 2


async def test_duplicate_connections_are_owner_scoped_and_serialized(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'duplicates.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    app = create_app(config={"database": {"url": url}})
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        alice = await auth(client, "duplicate-alice@test")
        bob = await auth(client, "duplicate-bob@test")
        base = "/mcp/connections"
        replies = await asyncio.gather(
            *[client.post(base, headers=alice, json=body()) for _ in range(2)]
        )
        assert sorted(reply.status_code for reply in replies) == [200, 409]
        first = next(reply.json()["data"] for reply in replies if reply.status_code == 200)
        assert (await client.post(base, headers=bob, json=body())).status_code == 200
        assert (
            await client.post(base, headers=alice, json=body(name="另一个名字", enabled=False))
        ).status_code == 409
        assert (
            await client.put(base + "/" + first["id"], headers=alice, json=body())
        ).status_code == 200
        other = (
            await client.post(base, headers=alice, json=body(url="http://localhost/other"))
        ).json()["data"]
        assert (
            await client.put(base + "/" + other["id"], headers=alice, json=body())
        ).status_code == 409
