import asyncio
from pathlib import Path

import httpx
from sqlalchemy import text

from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head


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
    ):
        operation = paths[base + suffix][method]
        assert "401" in operation["responses"]
        assert ("403" in operation["responses"]) == bool(suffix)
        assert operation["security"]


async def test_chat_lifecycle_and_rollback(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'chat.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    app = create_app(config={"database": {"url": url}})
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
