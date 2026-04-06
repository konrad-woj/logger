"""Tests for the logger package."""

import logging

import pytest
import structlog

from logger import configure_logging


@pytest.fixture(autouse=True)
def reset_structlog() -> None:
    """Reset structlog configuration between tests."""
    structlog.reset_defaults()


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


def test_log_level_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG
