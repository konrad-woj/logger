"""Light integration with Azure Monitor / Application Insights.

Requires the optional ``azure-monitor-opentelemetry`` dependency (``pip install 'logger[azure]'``).
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)

_NOISY_AZURE_LOGGERS = {
    "azure.core.pipeline.policies.http_logging_policy": logging.WARNING,
    "azure.monitor.opentelemetry.exporter": logging.WARNING,
    "azure.monitor.opentelemetry.exporter._quickpulse": logging.ERROR,
}

_configured = False


def configure_azure_monitor(connection_string: str | None = None) -> None:
    """Attach an Application Insights logging handler alongside stdout logging.

    Call once at startup, after ``logger.configure_logging()``. Requires the ``azure`` extra.

    No-ops with a warning if ``OTEL_SDK_DISABLED=true`` — that's the standard OpenTelemetry kill
    switch, an explicit request to disable telemetry, not a misconfiguration. Safe to call more
    than once; only the first call takes effect.

    Args:
        connection_string: App Insights connection string. If omitted, read from the
            ``APPLICATIONINSIGHTS_CONNECTION_STRING`` env var.

    Raises:
        ImportError: if the ``azure`` extra is not installed.
        RuntimeError: if ``APPLICATIONINSIGHTS_CONNECTION_STRING`` (or *connection_string*) is unset.
            Azure Monitor logging was explicitly requested, so a missing connection string is a
            deployment misconfiguration — fail loudly rather than silently running without telemetry.
    """
    global _configured
    if _configured:
        return

    resolved_connection_string = connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not resolved_connection_string:
        raise RuntimeError(
            "Azure Monitor logging was requested but APPLICATIONINSIGHTS_CONNECTION_STRING is unset. "
            "Set it (or pass connection_string=) before calling configure_azure_monitor()."
        )

    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        _log.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING is set but OTEL_SDK_DISABLED=true - "
            "Azure Monitor will not receive any telemetry. Unset OTEL_SDK_DISABLED to re-enable."
        )
        return

    try:
        from azure.monitor.opentelemetry import (  # pyright: ignore[reportMissingImports]
            configure_azure_monitor as _configure,
        )
    except ImportError as exc:
        raise ImportError(
            "azure-monitor-opentelemetry is required for logger.integrations.azure; "
            "install it with: pip install 'logger[azure]'"
        ) from exc

    _configure(logger_name="", connection_string=resolved_connection_string)  # "" = root logger

    for logger_name, level in _NOISY_AZURE_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(level)

    _configured = True
    _log.info("Azure Monitor telemetry configured.")
