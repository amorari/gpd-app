"""High-level iteration of GPD's top-level menu bar via AX."""
from __future__ import annotations

from typing import Iterator

from gpd_tests.drivers.ax import AXClient


class Menu:
    """Wraps AXClient for menu-level iteration.

    Intended for Phase 5 broad coverage: iterate every (menu, item) pair
    in GPD's menu bar, filter as needed, then pass to test parametrization.
    """

    # macOS adds an implicit "Apple" menu (system-wide); we filter it out
    # to stay scoped to GPD's own menu bar.
    SYSTEM_MENUS = {"Apple"}

    def __init__(self, ax: AXClient) -> None:
        self._ax = ax

    def top_level(self) -> list[str]:
        """All GPD-owned top-level menus, stable order."""
        return [m for m in self._ax.top_level_menus() if m not in self.SYSTEM_MENUS]

    def pairs(self) -> Iterator[tuple[str, str]]:
        """Yield (menu, item) for every item under every top-level menu.

        Skips items with an empty name and separator entries (AppleScript
        `missing value`); AXClient.items_of already filters those.
        """
        for menu in self.top_level():
            for item in self._ax.items_of(menu):
                yield menu, item

    def enabled_pairs(self) -> Iterator[tuple[str, str]]:
        """Yield (menu, item) only for items that are currently enabled."""
        for menu in self.top_level():
            for item in self._ax.enabled_items_of(menu):
                yield menu, item
