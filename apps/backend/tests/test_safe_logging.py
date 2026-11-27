import logging

import pytest

from super_ai.safe_logging import log_failure


def test_exception_logs_omit_sensitive_messages(caplog: pytest.LogCaptureFixture) -> None:
    secret = "sentinel-private-token"
    logger = logging.getLogger("test.safe_failure")
    try:
        try:
            raise ValueError(secret)
        except ValueError:
            raise RuntimeError("https://private.invalid/?token=" + secret) from None
    except RuntimeError as exc:
        log_failure(logger, "mcp_discovery", exc)
    assert secret not in caplog.text
    assert "private.invalid" not in caplog.text
    assert "exception_type=RuntimeError" in caplog.text
    assert "exception_type=ValueError" in caplog.text
    assert "stage=mcp_discovery" in caplog.text
    assert "test_safe_logging.py:" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_safe_code_is_retained(caplog: pytest.LogCaptureFixture) -> None:
    log_failure(logging.getLogger("test.safe_failure"), "job_handler", RuntimeError("MCP_TIMEOUT"))
    assert "code=MCP_TIMEOUT" in caplog.text
