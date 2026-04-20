import os

import pytest


@pytest.mark.smoke
@pytest.mark.real_backend
@pytest.mark.skipif(
    not os.environ.get("GPD_TEST_ANTHROPIC_KEY"),
    reason="GPD_TEST_ANTHROPIC_KEY not set",
)
def test_providers_non_empty(http):
    providers = http.providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1, "expected at least one provider when key is set"
