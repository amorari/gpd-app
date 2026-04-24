import json
import os
from pathlib import Path

import pytest

from gpd_tests.drivers.mcp import MCPError, MCPTimeout
from gpd_tests.pages.onboarding import sentinel_path


def _auth_json_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "opencode" / "auth.json"


@pytest.mark.smoke
@pytest.mark.xfail(
    reason=(
        "Passes standalone against a cold-start GPD but is order-fragile in "
        "a full-suite run: earlier smoke tests (sidebar, menu bar, etc.) "
        "navigate the webview off the welcome route / unmount the welcome "
        "component, so by the time this test runs the welcome title is no "
        "longer in document.body.innerText even though auth.json is still "
        "absent. A product-side fix (idempotent /route back to welcome when "
        "auth.json is missing on focus) would stabilise this; for now we "
        "xfail rather than add a destructive tier(3) that would wipe "
        "auth.json for every subsequent test."
    ),
    strict=False,
)
def test_welcome_screen_renders_when_sentinel_absent(mcp):
    """If `.gpd-initialized` is absent AND auth.json is absent, welcome text
    should be in the DOM.

    GPD renders welcome only when BOTH the sentinel is absent AND no stored
    API key is present (post-upstream TOS work: welcome is a two-step
    key→TOS gate, skipped entirely when a key is already on disk). A key
    present with sentinel absent is a post-onboarding-failure state, not a
    first-run state — the welcome surface won't render there.

    This test does NOT delete either file (that would force first-run for
    all subsequent tests); it only checks the current state. The dedicated
    first-run flow test in tests/flows/test_onboarding.py actively forces
    the state via @pytest.mark.tier(3) paired with clean_onboarding_state
    to restore auth.json on teardown.
    """
    if sentinel_path().exists():
        pytest.skip("already initialized; no welcome gate to check")
    if _auth_json_path().exists():
        pytest.skip(
            "auth.json present; welcome gate is skipped when a key is stored"
        )
    from gpd_tests.helpers.selectors import TEXT_WELCOME_TITLE

    # Check the welcome title — it renders as visible text. The API-key
    # placeholder is only in an <input placeholder=…> attribute and so
    # never appears in document.body.innerText.
    needle = TEXT_WELCOME_TITLE
    js = f'!!document.body && document.body.innerText.includes({json.dumps(needle)})'
    try:
        result = mcp.execute_js(js)
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert result in ("true", True, "True"), (
        f"welcome title {needle!r} not in body.innerText"
    )
