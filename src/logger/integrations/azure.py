"""Light integration with Azure Monitor / Application Insights.

Requires the optional ``azure-monitor-opentelemetry`` dependency (``pip install 'logger[azure]'``).
"""

from __future__ import annotations


def configure_azure_monitor(connection_string: str | None = None) -> None:
    """Attach an Application Insights logging handler alongside stdout logging.

    Call once at startup, after ``logger.configure_logging()``. Requires the ``azure`` extra.

    Args:
        connection_string: App Insights connection string. If omitted, read from the
            ``APPLICATIONINSIGHTS_CONNECTION_STRING`` env var.

    Raises:
        ImportError: if ``connection_string`` is not provided.
    """
    try:
        from azure.monitor.opentelemetry import (  # pyright: ignore[reportMissingImports]
            configure_azure_monitor as _configure,
        )
    except ImportError as exc:
        raise ImportError(
            "azure-monitor-opentelemetry is required for logger.integrations.azure; "
            "install it with: pip install 'logger[azure]'"
        ) from exc

    kwargs = {"connection_string": connection_string} if connection_string else {}
    _configure(logger_name="", **kwargs)  # "" = root logger, so it captures every stdlib logger
