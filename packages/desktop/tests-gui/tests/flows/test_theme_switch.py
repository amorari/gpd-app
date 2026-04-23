"""Phase 3 flow: toggling theme updates localStorage AND the rendered DOM.

Previously this test only round-tripped localStorage, which is a browser-API
tautology — it could pass even if GPD had no theme system at all. Now it
also verifies that ``document.documentElement`` reflects the theme change
via class name or ``data-theme`` attribute, which is what a user actually
sees.
"""
from __future__ import annotations

import json
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


_STORAGE_KEY = "opencode-color-scheme"


def _read_html_theme(probe: DOMProbe) -> tuple[str, str]:
    """Return (class_list, data_theme_attr) on <html> — both can signal theme."""
    try:
        class_list = probe.eval(
            "document.documentElement.className || ''"
        )
        data_theme = probe.eval(
            'document.documentElement.getAttribute("data-theme") || ""'
        )
    except ProbeSkip as e:
        pytest.skip(f"DOM probe unavailable ({e})")
    return str(class_list), str(data_theme)


@pytest.mark.flows
def test_theme_toggle_updates_storage_and_html_element(mcp):
    """Toggle color scheme and assert both storage AND the rendered <html> change."""
    probe = DOMProbe(mcp)
    try:
        before = probe.eval(
            f'JSON.stringify(localStorage.getItem("{_STORAGE_KEY}"))'
        )
    except ProbeSkip as e:
        pytest.skip(f"DOM probe unavailable ({e})")
    before_value = json.loads(before)

    if before_value not in (None, "dark", "light"):
        pytest.skip(
            f"{_STORAGE_KEY} is {before_value!r} (custom/system/auto); "
            "skipping to avoid overwriting an unrecognised setting"
        )

    html_class_before, html_theme_before = _read_html_theme(probe)

    # Toggle to the opposite value.
    next_value = "light" if before_value in (None, "dark") else "dark"

    try:
        probe.eval(
            f'localStorage.setItem("{_STORAGE_KEY}", "{next_value}"); '
            'window.dispatchEvent(new Event("storage"));'
        )

        # 1. Storage round-trip (the weakest check; always works).
        after = probe.eval(
            f'JSON.stringify(localStorage.getItem("{_STORAGE_KEY}"))'
        )
        after_value = json.loads(after)
        assert after_value == next_value, (
            f"expected storage {next_value!r}, got {after_value!r}"
        )

        # 2. DOM reactivity — the real UI check.
        # GPD's theme system listens on `storage` event + mounts a reactive
        # effect that updates documentElement.classList (typically "dark"/"light")
        # or sets data-theme. Give SolidJS a tick to react.
        deadline = time.monotonic() + 2.0
        html_changed = False
        html_class_after = html_class_before
        html_theme_after = html_theme_before
        while time.monotonic() < deadline:
            html_class_after, html_theme_after = _read_html_theme(probe)
            if (html_class_after != html_class_before or
                html_theme_after != html_theme_before):
                html_changed = True
                break
            time.sleep(0.1)

        # At least one signal (class list or data-theme) must reflect the
        # new scheme. If neither changed, the "theme" toggle was a no-op
        # from the user's perspective.
        if not html_changed:
            # It's possible the current HTML class already matches next_value
            # (e.g. system preference), in which case no change is expected.
            # Accept that case only if the class/attr already contains the
            # target word.
            matches_now = (
                next_value in html_class_after.lower()
                or next_value in html_theme_after.lower()
            )
            assert matches_now, (
                f"theme toggle did not update <html> — "
                f"class_before={html_class_before!r} class_after={html_class_after!r} "
                f"data-theme_before={html_theme_before!r} data-theme_after={html_theme_after!r}"
            )
    finally:
        # Restore — don't leave the dev's GPD with a toggled theme even on failure.
        try:
            if before_value is None:
                probe.eval(f'localStorage.removeItem("{_STORAGE_KEY}")')
            else:
                safe = before_value.replace('"', '\\"')
                probe.eval(
                    f'localStorage.setItem("{_STORAGE_KEY}", "{safe}")'
                )
            probe.eval('window.dispatchEvent(new Event("storage"));')
        except Exception:
            pass
