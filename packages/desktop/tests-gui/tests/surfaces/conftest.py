"""Fixtures shared by Phase 2 surface tests."""
from __future__ import annotations

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe
from gpd_tests.helpers.navigator import Navigator


@pytest.fixture
def nav(mcp) -> Navigator:
    return Navigator(mcp)


@pytest.fixture
def dom(mcp) -> DOMProbe:
    return DOMProbe(mcp)


