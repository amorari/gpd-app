"""Conftest for harness_selftest suite.

Imports are intentionally minimal at module scope so this suite remains
runnable even when other harness pieces are broken.  Any fixture that
needs a heavy import should do it inside the fixture body.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def tests_root():
    """Return the path to the tests-gui root directory."""
    from pathlib import Path
    return Path(__file__).resolve().parent.parent.parent
