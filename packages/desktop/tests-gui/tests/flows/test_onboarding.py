"""Phase 3 flow: first-run welcome → paste API key → reach home.

Gating (post G6.1):
  - ``@pytest.mark.real_backend`` — skipped unless GPD key is in auth.json
    is set (via the ``gpd_key`` fixture); the flow writes the key to
    auth.json so a real (non-stub) key is required.
  - ``@pytest.mark.tier(3)`` — before this test runs,
    ``conftest.pytest_runtest_setup`` calls ``scripts.reset.run(tier=3, ...)``
    which STOPS GPD, deletes tier-1/2/3 paths (sqlite + ``~/Library/*/<bundle>``
    + ``$XDG_DATA_HOME/opencode/auth.json`` + the
    ``~/.config/gpd/.gpd-initialized`` sentinel), then restarts GPD.
    auth.json and the sentinel BOTH need to be gone before GPD boots, else
    the welcome screen is skipped. tier(2)/fresh_app is insufficient
    because it no longer wipes auth.json (credential ≠ fresh-app state).
  - ``clean_onboarding_state`` fixture — restore-on-teardown safety net:
    snapshots whatever auth.json / sentinel existed before the test (tier-3
    may have already deleted them, in which case this is a no-op) and
    restores on exit. Redundant with the tier-3 pre-deletion, but cheap.
"""
from __future__ import annotations

import pytest

from gpd_tests.pages.onboarding import Onboarding, sentinel_path


@pytest.mark.xfail(
    reason=(
        "Product-dependent: after upstream's click-wrap TOS gate landed "
        "(5a0dc6738 + 5156fc014) the welcome flow became a two-step key→TOS "
        "form. The driver's shortcut (pre-set localStorage[gpd.tos.acceptedVersion] "
        "before key submit) depends on postTosAccept reaching the LiteLLM "
        "/gpd/tos-accept endpoint; the round-trip is flaky in unattended runs "
        "because a rejected or slow POST falls back to showing the TOS step, "
        "which needs bespoke DOM driving (scroll both text blocks to bottom + "
        "check both checkboxes + click 'I Agree'). Unxfail when either (a) the "
        "test driver scripts the full TOS click-wrap, or (b) the product grows "
        "a test-only bypass that can be flipped without network."
    ),
    strict=False,
)
@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.tier(3)
def test_first_run_paste_key_reach_home(
    mcp, gpd_key, clean_onboarding_state, app_state
):
    # Precondition: tier(3) + clean_onboarding_state ensure GPD restarted
    # with sentinel absent and auth.json removed.
    sentinel = sentinel_path()
    assert not sentinel.exists(), (
        "tier-3 reset did not remove the sentinel — "
        "scripts/reset.py may have drifted from the spec"
    )

    onboarding = Onboarding(mcp)
    assert onboarding.welcome_visible(), (
        "welcome screen not visible after tier-3 reset; "
        "GPD may have cached initialized state beyond the wiped paths"
    )

    onboarding.enter_api_key(gpd_key)
    onboarding.wait_for_home(timeout_s=30.0)

    # Post-condition: sentinel present, auth.json populated.
    assert sentinel_path().exists(), "sentinel not created after onboarding"
    assert clean_onboarding_state.exists(), "auth.json not created after onboarding"
