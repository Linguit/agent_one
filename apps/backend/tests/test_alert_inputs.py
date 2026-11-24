import importlib.util
import logging
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from super_ai.alert_api import get_alert_aggregator
from super_ai.alert_inputs import AlertAggregator, AlertSource, AlertsUnavailable
from super_ai.auth import current_user
from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head
from super_ai.project_config import JsonObject, JsonValue

ROOT = Path(__file__).resolve().parents[3]


def cls_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cls_generator", ROOT / "scripts/generate_and_upload_cls_logs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config() -> JsonObject:
    return {
        "prometheusAlerts": {
            "sources": [
                {
                    "name": "prom",
                    "type": "prometheus-v1",
                    "url": "https://prom.test/api/v1/alerts",
                    "timeout": 2,
                    "basicAuth": {"username": "private-user", "password": "private-secret"},
                },
                {"name": "am", "type": "alertmanager-v2", "url": "https://am.test/api/v2/alerts"},
            ]
        }
    }


def payload(prom: bool = True) -> Any:
    alert = {
        "labels": {
            "alertname": "HighCPU",
            "service": "api",
            "severity": "warning",
            "token": "private-token",
        },
        "annotations": {"summary": "private-secret bearer PRIVATE"},
        "nested": {"password": "hidden"},
    }
    if prom:
        return {
            "status": "success",
            "data": {"alerts": [{**alert, "state": "firing", "activeAt": "2026-11-23T00:00:00Z"}]},
        }
    return [{**alert, "status": {"state": "suppressed"}, "startsAt": "2026-11-23T00:00:00Z"}]


async def test_payload_auth_timeout_redaction(caplog: pytest.LogCaptureFixture) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        prom = request.url.host == "prom.test"
        if prom:
            assert request.headers["authorization"].startswith("Basic ")
            assert request.extensions["timeout"]["read"] == 2
        return httpx.Response(200, json=payload(prom))

    caplog.set_level(logging.DEBUG)
    result = await AlertAggregator(config(), httpx.MockTransport(respond)).active()
    assert [row.source for row in result.items] == ["prom", "am"]
    assert [row.status for row in result.items] == ["firing", "suppressed"]
    assert result.items[0].service == "api"
    assert result.items[1].startsAt == "2026-11-23T00:00:00Z"
    text = result.model_dump_json() + caplog.text
    for secret in ("private-secret", "private-token", "hidden", "PRIVATE"):
        assert secret not in text
    assert result.model_dump().keys() == {"items"}


@pytest.mark.parametrize("failure", ["timeout", "http", "schema", "config"])
async def test_one_source_failure(failure: str) -> None:
    cfg: JsonObject = config()
    if failure == "config":
        cfg = {
            "prometheusAlerts": {
                "sources": [
                    {"name": "bad", "type": "bad", "url": "not-url"},
                    {
                        "name": "am",
                        "type": "alertmanager-v2",
                        "url": "https://am.test/api/v2/alerts",
                    },
                ]
            }
        }

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.host == "prom.test":
            if failure == "timeout":
                raise httpx.ReadTimeout("private-secret", request=request)
            return httpx.Response(503 if failure == "http" else 200, json={})
        return httpx.Response(200, json=payload(False))

    result = await AlertAggregator(cfg, httpx.MockTransport(respond)).active()
    assert [row.source for row in result.items] == ["am"]


async def test_empty_success_and_all_failure() -> None:
    bodies: list[JsonValue] = [[], {"status": "success", "data": {"alerts": []}}]
    for body in bodies:

        def respond(request: httpx.Request, body: JsonValue = body) -> httpx.Response:
            if (request.url.host == "am.test") == isinstance(body, list):
                return httpx.Response(200, json=body)
            return httpx.Response(500)

        assert (await AlertAggregator(config(), httpx.MockTransport(respond)).active()).items == []
    with pytest.raises(AlertsUnavailable):
        await AlertAggregator(config(), httpx.MockTransport(lambda _: httpx.Response(500))).active()
    with pytest.raises(AlertsUnavailable):
        await AlertAggregator({}).active()


@pytest.mark.parametrize(
    "updates",
    [
        {"url": "https://user:secret@prom.test/"},
        {"url": "file:///private"},
        {"url": "https://prom.test/?token=secret"},
        {"timeout": 0},
        {"timeout": 121},
        {"type": "fake"},
    ],
)
def test_source_validation(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AlertSource.model_validate(
            {
                "name": "s",
                "type": "prometheus-v1",
                "url": "https://prom.test/api/v1/alerts",
                **updates,
            }
        )


async def test_authenticated_global_api(tmp_path: Path) -> None:
    db = f"sqlite+aiosqlite:///{(tmp_path / 'alerts.db').as_posix()}"
    upgrade_head(db, ROOT / "apps/backend")
    cfg: JsonObject = config()
    cfg["database"] = {"url": db}
    app = create_app(config=cfg)
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=payload(request.url.host == "prom.test"))

    app.dependency_overrides[get_alert_aggregator] = lambda: AlertAggregator(
        cfg, httpx.MockTransport(respond)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert calls == []
        assert (await client.get("/aiops/alerts/active")).status_code == 401
        assert calls == []
        results: list[Any] = []
        for email in ("one@alerts.test", "two@alerts.test"):
            body = {"email": email, "password": "test-password-123"}
            assert (await client.post("/auth/register", json=body)).status_code == 200
            token = (await client.post("/auth/login", json=body)).json()["data"]["token"]
            response = await client.get(
                "/aiops/alerts/active", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            results.append(response.json()["data"])
        assert results[0] == results[1]
        app.dependency_overrides[get_alert_aggregator] = lambda: AlertAggregator({})
        response = await client.get(
            "/aiops/alerts/active", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AIOPS_ALERTS_UNAVAILABLE"

        async def forbidden() -> dict[str, str]:
            raise HTTPException(403, "AUTH_FORBIDDEN")

        app.dependency_overrides[current_user] = forbidden
        assert (await client.get("/aiops/alerts/active")).status_code == 403
    schema = app.openapi()
    operation = schema["paths"]["/aiops/alerts/active"]["get"]
    assert {"200", "401", "403", "503"} <= operation["responses"].keys()
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"source", "status", "raw"} <= schema["components"]["schemas"]["Alert"][
        "properties"
    ].keys()


def upload_config() -> JsonObject:
    return {
        "cls": {"secretId": "PRIVATE_ID", "secretKey": "PRIVATE_KEY"},
        "clsLogUpload": {
            "endpoint": "https://ap-guangzhou.cls.tencentcs.com",
            "region": "ap-beijing",
            "topicId": "12345678-1234-1234-1234-123456789abc",
            "logsetId": "manual-only",
        },
    }


class Added:
    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self) -> Any:
        row = SimpleNamespace(logs=Added(), contents=Added())
        self.rows.append(row)
        return row


def test_cls_payload_count_route_and_preview(capsys: pytest.CaptureFixture[str]) -> None:
    tool = cls_tool()
    calls: list[Any] = []

    def client_factory(*args: Any) -> Any:
        calls.append(args)

        def put_log_raw(*values: Any) -> None:
            calls.append(values)

        return SimpleNamespace(put_log_raw=put_log_raw)

    def groups_factory() -> Any:
        return SimpleNamespace(logGroupList=Added())

    cfg = upload_config()
    assert tool.run(cfg, 3, client_factory=client_factory) == 0
    assert calls == []
    assert (
        tool.run(
            cfg,
            3,
            "https://ap-guangzhou.cls.tencentcs.com",
            "12345678-1234-1234-1234-123456789abc",
            client_factory,
            groups_factory,
        )
        == 0
    )
    assert calls[0][0] == "https://ap-guangzhou.cls.tencentcs.com"
    assert len(calls[0]) == 3  # region/logsetId 不作为 SDK 路由参数
    topic, groups = calls[1]
    assert topic == "12345678-1234-1234-1234-123456789abc"
    logs = groups.logGroupList.rows[0].logs.rows
    assert len(logs) == 3
    fields = {field.key: field.value for field in logs[0].contents.rows}
    assert fields["region"] == "ap-beijing"
    assert "manual-only" not in str(fields)
    assert logs[0].time > 10**15
    assert "PRIVATE" not in capsys.readouterr().out
    assert len(tool.generate_logs(1000, "ap-beijing")) == 1000


@pytest.mark.parametrize("count", [0, -1, 1001, True])
def test_cls_invalid_count(count: int) -> None:
    with pytest.raises(ValueError):
        cls_tool().run(upload_config(), count)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://ap-guangzhou.cls.tencentcs.com",
        "https://evil.test",
        "https://ap-guangzhou.cls.tencentcs.com/path",
        "https://user:secret@ap-guangzhou.cls.tencentcs.com",
        "https://ap-guangzhou.cls.tencentcs.com:443",
        "https://ap-guangzhou.cls.tencentcs.com?token=x",
    ],
)
def test_cls_endpoint_validation(endpoint: str) -> None:
    cfg = upload_config()
    cfg["clsLogUpload"] = {"endpoint": endpoint, "region": "ap-beijing", "topicId": "bad"}
    with pytest.raises(ValueError):
        cls_tool().run(cfg, 1)


def test_cls_confirmation_and_error_privacy(capsys: pytest.CaptureFixture[str]) -> None:
    tool = cls_tool()
    with pytest.raises(ValueError):
        tool.run(upload_config(), 1, "wrong", "wrong")

    def fail(*args: Any) -> Any:
        raise RuntimeError("PRIVATE_KEY")

    with pytest.raises(ValueError) as error:
        tool.run(
            upload_config(),
            1,
            "https://ap-guangzhou.cls.tencentcs.com",
            "12345678-1234-1234-1234-123456789abc",
            fail,
            lambda: SimpleNamespace(logGroupList=Added()),
        )
    assert "PRIVATE" not in str(error.value) + capsys.readouterr().out


def test_import_has_no_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("import attempted external operation")

    monkeypatch.setattr("super_ai.project_config.load_project_config", fail)
    monkeypatch.setattr(httpx.AsyncClient, "get", fail)
    tool = cls_tool()
    assert callable(tool.main)
    create_app(config={})
