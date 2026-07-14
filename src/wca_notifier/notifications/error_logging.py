from __future__ import annotations

import logging
from typing import Any


def log_delivery_failure(
    logger: logging.Logger,
    *,
    channel: str,
    event_key: str,
    error: Exception,
) -> None:
    """Log delivery metadata without serializing credential-bearing URLs."""
    response: Any = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        logger.error(
            "%s delivery failed for %s (%s)",
            channel,
            event_key,
            type(error).__name__,
        )
        return
    logger.error(
        "%s delivery failed for %s (%s, HTTP %s)",
        channel,
        event_key,
        type(error).__name__,
        status_code,
    )
