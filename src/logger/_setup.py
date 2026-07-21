"""Internal structlog configuration — not part of the public API."""

import logging
import os
from typing import Literal

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import Processor

LogProvider = Literal["generic", "gcp", "aws", "azure"]


def _build_processors(is_production: bool, provider: LogProvider) -> list[Processor]:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        shared.append(structlog.processors.dict_tracebacks)
        if provider == "gcp":
            from logger.integrations.gcp import rename_for_gcp

            shared.append(rename_for_gcp)
        shared.append(structlog.processors.JSONRenderer())
    else:
        shared += [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    return shared  # type: ignore[return-value]


def configure_logging(provider: LogProvider | None = None) -> None:
    """Configure structlog and the stdlib logging bridge.

    Call once at application startup — typically in ``main.py`` or the FastAPI lifespan handler — before any logger.

    Reads two environment variables:

    - ``LOG_ENV``: set to ``production`` for JSON output; anything else (or unset) gives coloured console output.
    - ``LOG_LEVEL``: stdlib level name (e.g. ``DEBUG``, ``INFO``).  Defaults to ``INFO``.

    Args:
        provider: Target log backend, or ``None`` to read ``LOG_PROVIDER`` (default ``"generic"``).
    """
    is_production = os.getenv("LOG_ENV", "").lower() == "production"
    resolved_provider: LogProvider = (provider or os.getenv("LOG_PROVIDER", "generic")).lower()  # type: ignore[assignment]
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if level is None:
        logging.warning("LOG_LEVEL=%r is not a valid level name; defaulting to INFO", level_name)
        level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        level=level,
    )
    logging.getLogger().setLevel(level)

    processors = _build_processors(is_production, resolved_provider)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Return a structlog BoundLogger bound to *name*.

    Args:
        name: Logger name — pass ``__name__`` from the calling module.

    Returns:
        A structlog ``BoundLogger`` instance.
    """
    return structlog.get_logger(name)  # type: ignore[return-value]
