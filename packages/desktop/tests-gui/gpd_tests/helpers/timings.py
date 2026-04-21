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
    predicate: Callable[[], bool],
    *,
    timeout_s: float,
    poll_s: float = 0.1,
    reraise_on_timeout: bool = False,
) -> bool:
    """Poll `predicate` until it returns truthy or timeout. Return last value.

    Parameters
    ----------
    predicate:
        Callable returning a truthy value when the condition is met.
    timeout_s:
        Maximum wall-clock seconds to wait.
    poll_s:
        Seconds between polls.
    reraise_on_timeout:
        When *True*, if the predicate kept raising exceptions and the deadline
        fires, re-raise the *last* exception instead of returning ``False``.
        Useful for surfacing unexpected errors rather than silently converting
        them to a timeout.
    """
    deadline = time.monotonic() + timeout_s
    last_exc: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
            last_exc = None  # predicate ran cleanly; clear any prior exception
        except Exception as exc:
            last_exc = exc
        time.sleep(poll_s)
    # Deadline reached — do NOT run a post-deadline final check (it can burn
    # additional time when the predicate itself is slow).
    if reraise_on_timeout and last_exc is not None:
        raise last_exc
    return False
