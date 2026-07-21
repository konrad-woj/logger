"""Light integration with Google Cloud Logging's structured JSON convention.
See https://cloud.google.com/logging/docs/structured-logging#special-payload-fields

``configure_logging(provider="gcp")`` wires ``rename_for_gcp`` in automatically;
use ``bind_trace`` per-request to correlate log lines with a Cloud Trace span.
"""

from __future__ import annotations

import structlog
from structlog.types import EventDict, WrappedLogger

_GCP_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
}


def rename_for_gcp(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """Rewrite structlog's default keys into GCP Cloud Logging's special fields.

    - ``event`` -> ``message`` (populates the LogEntry summary line)
    - ``level`` -> ``severity`` (uppercased, mapped to the LogSeverity enum)
    - ``timestamp`` -> ``time`` (used as the LogEntry timestamp instead of ingestion time)
    """
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    level = event_dict.pop("level", None)
    if level is not None:
        event_dict["severity"] = _GCP_SEVERITY.get(level, level.upper())
    if "timestamp" in event_dict:
        event_dict["time"] = event_dict.pop("timestamp")
    return event_dict


def bind_trace(project_id: str, trace_id: str, span_id: str | None = None) -> None:
    """Bind the active trace/span so log lines correlate with a Cloud Trace span.

    Call once per request/task with values parsed from the incoming
    ``X-Cloud-Trace-Context`` header (or the active OpenTelemetry span).

    Args:
        project_id: GCP project ID that owns the trace.
        trace_id: Trace ID, as found in ``X-Cloud-Trace-Context``.
        span_id: Optional span ID within the trace.
    """
    fields = {"logging.googleapis.com/trace": f"projects/{project_id}/traces/{trace_id}"}
    if span_id:
        fields["logging.googleapis.com/spanId"] = span_id
    structlog.contextvars.bind_contextvars(**fields)
