"""Tests for the Azure Monitor integration."""

import importlib.util
import subprocess
import sys
import textwrap

import pytest

from logger.integrations.azure import configure_azure_monitor

try:
    _AZURE_MONITOR_INSTALLED = importlib.util.find_spec("azure.monitor.opentelemetry") is not None
except ModuleNotFoundError:
    _AZURE_MONITOR_INSTALLED = False


@pytest.mark.skipif(_AZURE_MONITOR_INSTALLED, reason="azure-monitor-opentelemetry is installed")
def test_configure_azure_monitor_raises_actionable_error_without_extra() -> None:
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
