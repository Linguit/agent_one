from pathlib import Path

import httpx

from super_ai.auth import normalize_email, token_digest
from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head


def test_auth_security_primitives() -> None:
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert len(token_digest("opaque-token")) == 64
    assert token_digest("opaque-token") != "opaque-token"


async def test_auth_session_http_lifecycle(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    app = create_app(config={"database": {"url": url}})
    async with app.router.lifespan_context(app):
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
