"""Tests for the logger package."""

import io
import json
import logging

import pytest
import structlog

from logger import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_structlog() -> None:
    """Reset structlog configuration and context between tests."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def test_configure_dev_uses_console_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_ENV", raising=False)
    configure_logging()
    renderer_types = [type(p) for p in structlog.get_config()["processors"]]
    assert structlog.dev.ConsoleRenderer in renderer_types


def test_configure_prod_uses_json_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    configure_logging()
    renderer_types = [type(p) for p in structlog.get_config()["processors"]]
    assert structlog.processors.JSONRenderer in renderer_types


def test_configure_includes_merge_contextvars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_ENV", raising=False)
    configure_logging()
    processor_fns = [p for p in structlog.get_config()["processors"]]
    assert structlog.contextvars.merge_contextvars in processor_fns


def test_log_level_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_invalid_log_level_warns_and_defaults_to_info(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "TYPO")
    with caplog.at_level(logging.WARNING):
        configure_logging()
        assert logging.getLogger().level == logging.INFO
    assert any("TYPO" in r.message for r in caplog.records)


def test_prod_log_output_is_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_ENV", "production")
    configure_logging()

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        log = get_logger("test.module")
        log.info("order.placed", order_id="42", amount=9.99)
    finally:
        root.removeHandler(handler)

    line = buf.getvalue().strip()
    assert line, "expected log output"
    record = json.loads(line)
    assert record["event"] == "order.placed"
    assert record["order_id"] == "42"
    assert record["level"] == "info"
    assert record["logger"] == "test.module"


async def test_contextvars_isolated_across_async_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context bound via bind_contextvars must not bleed across concurrent tasks."""
    import asyncio

    monkeypatch.setenv("LOG_ENV", "production")
    configure_logging()

    results: dict[str, object] = {}

    async def task(name: str, value: str) -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=value)
        await asyncio.sleep(0)  # yield so tasks interleave
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            get_logger("test").info("ping")
        finally:
            root.removeHandler(handler)
        line = buf.getvalue().strip()
        record = json.loads(line)
        results[name] = record.get("request_id")

    await asyncio.gather(task("a", "req-A"), task("b", "req-B"))

    assert results["a"] == "req-A"
    assert results["b"] == "req-B"
