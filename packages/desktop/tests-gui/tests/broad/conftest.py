"""Ensure the 'broad' marker is registered even when pytest.ini hasn't been
updated yet (e.g. the T3 worktree hasn't landed its marker registration).

Without this, --strict-markers would reject @pytest.mark.broad at collection
time and break every other marker-filtered run (e.g. `pytest -m unit`).
"""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    known = {m.name for m in config._parser._inidict.get("markers", []) if hasattr(m, "name")}
    # Simpler: use the public API to check registered markers.
    try:
        registered = {m.split(":")[0].strip() for m in config.getini("markers")}
    except Exception:
        registered = set()
    if "broad" not in registered:
        config.addinivalue_line(
            "markers",
            "broad: Phase 5 broad sweep (requires GPD running)",
        )
