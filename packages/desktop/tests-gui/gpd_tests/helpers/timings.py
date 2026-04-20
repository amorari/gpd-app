"""Slow-mo and bounded-wait helpers."""
from __future__ import annotations

import os
import time
from typing import Callable


def slowmo_ms() -> int:
    """Per-action delay in ms. Env > CI default (0) > local default (200)."""
    raw = os.environ.get("PYTEST_SLOWMO_MS")
    if raw is not None:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    if os.environ.get("PYTEST_CI") == "1":
        return 0
    return 200


def slowmo_sleep() -> None:
    """Sleep for `slowmo_ms()`. Call after each driver action."""
    ms = slowmo_ms()
    if ms:
        time.sleep(ms / 1000.0)


def wait_until(
    predicate: Callable[[], bool], *, timeout_s: float, poll_s: float = 0.1
) -> bool:
    """Poll `predicate` until it returns truthy or timeout. Return last value."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(poll_s)
    try:
        return bool(predicate())
    except Exception:
        return False
