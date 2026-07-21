"""Tests for the AWS X-Ray trace binding integration."""

import io
import json
import logging

import pytest
import structlog

from logger import configure_logging, get_logger
from logger.integrations.aws import bind_xray_trace_from_env


@pytest.fixture(autouse=True)
def reset_structlog() -> None:
    """Reset structlog configuration and context between tests."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def test_bind_xray_trace_from_env_noop_without_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("_X_AMZN_TRACE_ID", raising=False)
    bind_xray_trace_from_env()
    assert structlog.contextvars.get_contextvars() == {}


def test_bind_xray_trace_from_env_binds_root_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("_X_AMZN_TRACE_ID", "Root=1-5e1b4151-5ac6c58dc39a3f2b8d0f5f1e;Parent=53995c3f42cd8ad8;Sampled=1")
    bind_xray_trace_from_env()
    assert structlog.contextvars.get_contextvars()["xray_trace_id"] == "1-5e1b4151-5ac6c58dc39a3f2b8d0f5f1e"


def test_xray_trace_id_appears_in_log_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    monkeypatch.setenv("_X_AMZN_TRACE_ID", "Root=1-abc;Parent=def;Sampled=1")
    configure_logging()
    bind_xray_trace_from_env()

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        get_logger("test").info("ping")
    finally:
        root.removeHandler(handler)

    record = json.loads(buf.getvalue().strip())
    assert record["xray_trace_id"] == "1-abc"
