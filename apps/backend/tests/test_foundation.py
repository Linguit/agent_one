import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from super_ai.main import create_app, get_project_config
from super_ai.project_config import ConfigError, JsonObject, deep_merge, load_project_config


def test_merge_is_recursive_and_does_not_mutate() -> None:
    base: JsonObject = {"nested": {"keep": 1, "replace": 2}, "items": [1], "value": 1}
    override: JsonObject = {"nested": {"replace": 3}, "items": [2], "value": None}
    before = json.dumps(base)
    merged = deep_merge(base, override)
    assert merged == {"nested": {"keep": 1, "replace": 3}, "items": [2], "value": None}
    assert json.dumps(base) == before
    assert deep_merge({"x": 1}, {"x": {"a": 2}}) == {"x": {"a": 2}}


def test_local_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "project.json").write_text('{"frontend":{"title":"base","x":1}}')
    (tmp_path / "user.project.json").write_text('{"frontend":{"title":"local"}}')
    monkeypatch.setenv("FRONTEND_TITLE", "must-not-be-used")
    monkeypatch.setenv("PROJECT_CONFIG", "must-not-be-used")
    assert load_project_config(tmp_path) == {"frontend": {"title": "local", "x": 1}}
    (tmp_path / "user.project.json").unlink()
    assert load_project_config(tmp_path) == {"frontend": {"title": "base", "x": 1}}


@pytest.mark.parametrize("content", ["[]", "null", '"private-value"', "{broken"])
def test_invalid_config_is_redacted(tmp_path: Path, content: str) -> None:
    (tmp_path / "project.json").write_text(content)
    with pytest.raises(ConfigError) as error:
        load_project_config(tmp_path)
    assert content not in str(error.value)


def test_missing_base_and_invalid_override(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="project.json"):
        load_project_config(tmp_path)
    (tmp_path / "project.json").write_text("{}")
    (tmp_path / "user.project.json").write_text("[]")
    with pytest.raises(ConfigError, match="user.project.json"):
        load_project_config(tmp_path)


async def test_health_and_dependency_injection(tmp_path: Path) -> None:
    (tmp_path / "project.json").write_text('{"test":"local"}')
    app = create_app(config_dir=tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["ok"] is True
    assert response.headers["X-Request-ID"] == response.json()["meta"]["requestId"]
    assert get_project_config(type_request(app)) == {"test": "local"}
    assert create_app(config={}).state.project_config == {}


def type_request(app: object):
    from starlette.requests import Request

    return Request({"type": "http", "app": app})


def test_all_modules_import_without_io(tmp_path: Path) -> None:
    code = """
import importlib, pkgutil, pathlib, socket, sqlite3, sys
import fastapi, sqlalchemy, sqlalchemy.ext.asyncio
def denied(*args, **kwargs):
    raise AssertionError("import side effect")
socket.socket = denied
socket.create_connection = denied
sqlite3.connect = denied
sqlalchemy.create_engine = denied
sqlalchemy.ext.asyncio.create_async_engine = denied
pathlib.Path.read_text = denied
import super_ai
assert "src/super_ai" in super_ai.__file__.replace("\\\\", "/")
for module in pkgutil.walk_packages(super_ai.__path__, "super_ai."):
    importlib.import_module(module.name)
assert not any(name in sys.modules for name in ("pymilvus", "langchain_openai", "mcp"))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
