"""Phase 3 flow: first-run welcome → paste API key → reach home."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from gpd_tests.pages.onboarding import Onboarding, SENTINEL


DESTRUCTIVE = os.environ.get("PYTEST_RUN_DESTRUCTIVE_FLOWS") == "1"


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.fresh_app
@pytest.mark.skipif(
    not DESTRUCTIVE,
    reason="onboarding mutates ~/.config/gpd and auth.json; "
    "opt in via PYTEST_RUN_DESTRUCTIVE_FLOWS=1",
)
def test_first_run_paste_key_reach_home(
    mcp, anthropic_key, clean_auth_json, app_state
):
    # Precondition: fresh_app + clean_auth_json ensure GPD restarted with
    # sentinel absent and auth.json removed.
    assert not SENTINEL.exists(), (
        "tier-2 reset did not remove the sentinel — "
        "scripts/reset.py may have drifted from the spec"
    )

    onboarding = Onboarding(mcp)
    assert onboarding.welcome_visible(), (
        "welcome screen not visible after fresh_app reset; "
        "tier-2 may not be forcing first-run"
    )

    onboarding.enter_api_key(anthropic_key)
    onboarding.wait_for_home(timeout_s=30.0)

    # Post-condition: sentinel present, auth.json populated.
    assert SENTINEL.exists(), "sentinel not created after onboarding"
    assert clean_auth_json.exists(), "auth.json not created after onboarding"
