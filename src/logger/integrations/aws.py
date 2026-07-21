"""Light integration with AWS CloudWatch Logs / X-Ray.
See https://docs.aws.amazon.com/xray/latest/devguide/xray-services-cloudwatchlogs.html
"""

from __future__ import annotations

import os

import structlog


def bind_xray_trace_from_env() -> None:
    """Bind the current X-Ray trace id (from ``_X_AMZN_TRACE_ID``) into context.

    Call once per invocation/request — e.g. at the top of a Lambda handler
    or in request middleware. No-ops if the env var isn't set (i.e.
    running outside Lambda/ECS or without X-Ray tracing enabled).
    """
    trace_header = os.getenv("_X_AMZN_TRACE_ID")
    if not trace_header:
        return
    for part in trace_header.split(";"):
        if part.startswith("Root="):
            structlog.contextvars.bind_contextvars(xray_trace_id=part.removeprefix("Root="))
            return
