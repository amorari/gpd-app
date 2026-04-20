"""Fixtures shared by Phase 5 broad/menu tests."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


@pytest.fixture
def axmenu(ax: AXClient) -> AXClient:
    """Alias for the root `ax` fixture with a name that signals intent
    for menu-iteration tests."""
    return ax
