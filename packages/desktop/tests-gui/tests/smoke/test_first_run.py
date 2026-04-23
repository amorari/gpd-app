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
    the state via @pytest.mark.tier(3).
    """
    if sentinel_path().exists():
        pytest.skip("already initialized; no welcome gate to check")
    if _auth_json_path().exists():
        pytest.skip(
            "auth.json present; welcome gate is skipped when a key is stored"
        )
    from gpd_tests.helpers.selectors import TEXT_WELCOME_API_KEY_PROMPT

    needle = TEXT_WELCOME_API_KEY_PROMPT
    js = f'!!document.body && document.body.innerText.includes({json.dumps(needle)})'
    try:
        result = mcp.execute_js(js)
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert result in ("true", True, "True")
