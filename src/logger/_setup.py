"""Internal structlog configuration — not part of the public API."""

import logging
import os

import structlog
from structlog.stdlib import BoundLogger
from structlog.types import Processor


def _build_processors(is_production: bool) -> list[Processor]:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        shared += [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        shared += [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    return shared  # type: ignore[return-value]


def configure_logging() -> None:
    """Configure structlog and the stdlib logging bridge.

    Call once at application startup — typically in ``main.py`` or the
    FastAPI lifespan handler — before any logger is used.

    Reads two environment variables:

    - ``LOG_ENV``: set to ``production`` for JSON output; anything else (or
      unset) gives coloured console output.
    - ``LOG_LEVEL``: stdlib level name (e.g. ``DEBUG``, ``INFO``).  Defaults
      to ``INFO``.
    """
    is_production = os.getenv("LOG_ENV", "").lower() == "production"
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

    processors = _build_processors(is_production)

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
