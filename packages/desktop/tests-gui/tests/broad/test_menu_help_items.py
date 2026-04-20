"""Help menu: has at least one item (Cocoa gives you a Search field for free)."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


@pytest.mark.broad
def test_help_menu_non_empty(ax: AXClient):
    items = ax.items_of("Help")
    assert items, (
        "Help menu has no items; AppKit usually exposes a Search field at "
        "minimum — this likely indicates an AX or menu-registration issue"
    )
