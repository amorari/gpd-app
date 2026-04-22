"""Fixtures scoped to stress / e2e stress tests."""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def anthropic_key() -> str:
    """Return the test-mode Anthropic key; skip if absent.

    Tests marked @pytest.mark.real_backend depend on this.
    """
    key = os.environ.get("GPD_TEST_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip(
            "GPD_TEST_ANTHROPIC_KEY not set; skipping real-backend flow"
        )
    return key
