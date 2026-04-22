"""Fixtures shared by Phase 2 surface tests."""
from __future__ import annotations

import os

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe
from gpd_tests.helpers.navigator import Navigator


@pytest.fixture
def nav(mcp) -> Navigator:
    return Navigator(mcp)


@pytest.fixture
def dom(mcp) -> DOMProbe:
    return DOMProbe(mcp)


@pytest.fixture
def anthropic_key() -> str:
    """Return the test-mode Anthropic key; skip if absent."""
    key = os.environ.get("GPD_TEST_ANTHROPIC_KEY")
    if not key:
        pytest.skip(
            "GPD_TEST_ANTHROPIC_KEY not set; skipping real-backend flow"
        )
    return key
