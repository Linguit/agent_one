import httpx

from super_ai.auth import auth_sessions, normalize_email, token_digest, users
from super_ai.main import create_app


def test_auth_security_primitives() -> None:
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert len(token_digest("opaque-token")) == 64
    assert token_digest("opaque-token") != "opaque-token"


async def test_auth_session_http_lifecycle() -> None:
    app = create_app(config={"database": {"url": "sqlite+aiosqlite:///:memory:"}})
    engine = app.state.db_engine
    try:
        async with engine.begin() as connection:
            await connection.run_sync(users.create)
            await connection.run_sync(auth_sessions.create)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            credentials = {"email": "shell@example.test", "password": "desktop-test-password"}
            registration = await client.post("/auth/register", json=credentials)
            assert registration.status_code == 200
            user = registration.json()["data"]
            login = await client.post("/auth/login", json=credentials)
            assert login.status_code == 200
            assert login.json()["data"]["user"] == user
            headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
            restored = await client.get("/auth/me", headers=headers)
            assert restored.status_code == 200
            assert restored.json()["data"] == user
            logout = await client.post("/auth/logout", headers=headers)
            assert logout.status_code == 200
            assert logout.json()["data"] == {"loggedOut": True}
            assert (await client.get("/auth/me", headers=headers)).status_code == 401
    finally:
        await engine.dispose()
