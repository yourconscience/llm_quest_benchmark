"""Langfuse tracing integration. Activates when LANGFUSE_SECRET_KEY is set."""

import os

_enabled: bool | None = None


def is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = bool(os.getenv("LANGFUSE_SECRET_KEY"))
    return _enabled


def flush() -> None:
    if not is_enabled():
        return
    from langfuse import Langfuse

    Langfuse().flush()
