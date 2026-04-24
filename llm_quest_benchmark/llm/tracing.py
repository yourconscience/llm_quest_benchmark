"""Langfuse tracing integration. Activates when LANGFUSE_SECRET_KEY is set."""

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def is_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


def flush() -> None:
    if not is_enabled():
        return
    try:
        from langfuse import Langfuse

        Langfuse().flush()
    except Exception:
        logger.debug("Langfuse flush failed", exc_info=True)
