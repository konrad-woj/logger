"""Tests for the Azure Monitor integration."""

import importlib.util
import logging
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from _azure_test_utils import reset_azure_module_state

import logger.integrations.azure as _azure
from logger.integrations.azure import configure_azure_monitor

try:
    _AZURE_MONITOR_INSTALLED = importlib.util.find_spec("azure.monitor.opentelemetry") is not None
except ModuleNotFoundError:
    _AZURE_MONITOR_INSTALLED = False


@pytest.fixture(autouse=True)
def reset_azure_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset the module-level idempotency flag and relevant env vars between tests."""
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    reset_azure_module_state()
    yield
    reset_azure_module_state()


@pytest.mark.skipif(_AZURE_MONITOR_INSTALLED, reason="azure-monitor-opentelemetry is installed")
def test_configure_azure_monitor_raises_actionable_error_without_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=fake")
    with pytest.raises(ImportError, match=r"logger\[azure\]"):
        configure_azure_monitor()


@pytest.mark.skipif(not _AZURE_MONITOR_INSTALLED, reason="azure-monitor-opentelemetry not installed")
def test_configure_azure_monitor_attaches_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_configure(**kwargs: object) -> None:
        calls.update(kwargs)

    monkeypatch.setattr("azure.monitor.opentelemetry.configure_azure_monitor", fake_configure)
    configure_azure_monitor(connection_string="InstrumentationKey=fake")

    assert calls["logger_name"] == ""
    assert calls["connection_string"] == "InstrumentationKey=fake"


def test_configure_azure_monitor_raises_when_connection_string_unset() -> None:
    with patch.dict("sys.modules", {"azure.monitor.opentelemetry": MagicMock()}):
        with pytest.raises(RuntimeError, match="APPLICATIONINSIGHTS_CONNECTION_STRING"):
            configure_azure_monitor()
    assert not _azure._configured


def test_configure_azure_monitor_otel_disabled_skips_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    mock_module = MagicMock()
    with patch.dict("sys.modules", {"azure.monitor.opentelemetry": mock_module}):
        configure_azure_monitor(connection_string="InstrumentationKey=fake")
    mock_module.configure_azure_monitor.assert_not_called()
    assert not _azure._configured


def test_configure_azure_monitor_silences_noisy_loggers() -> None:
    with patch.dict("sys.modules", {"azure.monitor.opentelemetry": MagicMock()}):
        configure_azure_monitor(connection_string="InstrumentationKey=fake")
    for logger_name, level in _azure._NOISY_AZURE_LOGGERS.items():
        assert logging.getLogger(logger_name).level == level


def test_configure_azure_monitor_only_configures_once() -> None:
    mock_configure = MagicMock()
    with patch.dict("sys.modules", {"azure.monitor.opentelemetry": MagicMock(configure_azure_monitor=mock_configure)}):
        configure_azure_monitor(connection_string="InstrumentationKey=fake")
        configure_azure_monitor(connection_string="InstrumentationKey=fake")
    mock_configure.assert_called_once()


@pytest.mark.skipif(not _AZURE_MONITOR_INSTALLED, reason="azure-monitor-opentelemetry not installed")
def test_configure_azure_monitor_real_sdk_attaches_handler() -> None:
    """Invoke the real azure-monitor-opentelemetry SDK, not a mock.

    Runs in a subprocess: ``configure_azure_monitor`` sets process-global
    OpenTelemetry state (tracer/logger providers) that can only be
    configured once per process, so calling the real SDK in-process would
    leak into every other test in this suite.
    """
    script = textwrap.dedent("""
        import logging
        import os
        from logger.integrations.azure import configure_azure_monitor

        configure_azure_monitor(connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000")
        handlers = logging.getLogger().handlers
        assert any(type(h).__name__ == "LoggingHandler" for h in handlers), handlers
        print("OK")
        os._exit(0)
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
