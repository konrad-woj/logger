"""Tests for the GCP logging integration."""

import io
import json
import logging

import pytest
import structlog

from logger import configure_logging, get_logger
from logger.integrations.gcp import bind_trace, rename_for_gcp


@pytest.fixture(autouse=True)
def reset_structlog() -> None:
    """Reset structlog configuration and context between tests."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def test_rename_for_gcp_maps_special_fields() -> None:
    event_dict = {"event": "order.placed", "level": "warning", "timestamp": "2024-11-05T12:00:00Z"}
    result = rename_for_gcp(None, "warning", event_dict)
    assert result == {"message": "order.placed", "severity": "WARNING", "time": "2024-11-05T12:00:00Z"}


def test_configure_logging_gcp_produces_gcp_shaped_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    configure_logging(provider="gcp")

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        log = get_logger("test.module")
        log.info("order.placed", order_id="42")
    finally:
        root.removeHandler(handler)

    record = json.loads(buf.getvalue().strip())
    assert record["message"] == "order.placed"
    assert record["severity"] == "INFO"
    assert "time" in record
    assert "event" not in record
    assert "level" not in record
    assert "timestamp" not in record


def test_log_provider_env_var_selects_gcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    monkeypatch.setenv("LOG_PROVIDER", "gcp")
    configure_logging()

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        get_logger("test").error("boom")
    finally:
        root.removeHandler(handler)

    record = json.loads(buf.getvalue().strip())
    assert record["severity"] == "ERROR"
    assert record["message"] == "boom"


def test_bind_trace_appears_in_log_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    configure_logging(provider="gcp")
    bind_trace(project_id="my-project", trace_id="abc123", span_id="1")

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
    assert record["logging.googleapis.com/trace"] == "projects/my-project/traces/abc123"
    assert record["logging.googleapis.com/spanId"] == "1"
