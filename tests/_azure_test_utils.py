"""Shared helper for resetting logger.integrations.azure module state between tests."""

import logging

import logger.integrations.azure as _azure


def reset_azure_module_state() -> None:
    """Reset the idempotency flag and noisy-logger levels set by configure_azure_monitor."""
    _azure._configured = False
    for logger_name in _azure._NOISY_AZURE_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.NOTSET)
