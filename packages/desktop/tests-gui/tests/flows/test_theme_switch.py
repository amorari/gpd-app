"""Phase 3 flow: toggling theme updates localStorage['opencode-color-scheme']."""
from __future__ import annotations

import json

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


@pytest.mark.flows
def test_theme_toggle_updates_local_storage(mcp):
    probe = DOMProbe(mcp)
    try:
        before = probe.eval(
            'JSON.stringify(localStorage.getItem("opencode-color-scheme"))'
        )
    except ProbeSkip as e:
        pytest.skip(f"DOM probe unavailable ({e})")
    before_value = json.loads(before)  # either null or a string

    # Toggle: if currently 'dark' or null → set 'light'; else → set 'dark'.
    next_value = "light" if before_value == "dark" else "dark"
    probe.eval(
        f'localStorage.setItem("opencode-color-scheme", "{next_value}"); '
        'window.dispatchEvent(new Event("storage"));'
    )

    after = probe.eval(
        'JSON.stringify(localStorage.getItem("opencode-color-scheme"))'
    )
    after_value = json.loads(after)
    assert after_value == next_value, (
        f"expected {next_value!r}, got {after_value!r}"
    )

    # Restore — don't leave the dev's GPD in a surprise theme.
    if before_value is None:
        probe.eval('localStorage.removeItem("opencode-color-scheme")')
    else:
        safe = before_value.replace('"', '\\"')
        probe.eval(f'localStorage.setItem("opencode-color-scheme", "{safe}")')
