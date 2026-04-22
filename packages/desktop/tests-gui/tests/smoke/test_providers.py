import os

import pytest


@pytest.mark.smoke
@pytest.mark.real_backend
@pytest.mark.skipif(
    not (os.environ.get("GPD_TEST_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")),
    reason="GPD_TEST_ANTHROPIC_KEY not set",
)
def test_providers_non_empty(http):
    data = http.providers()
    assert isinstance(data, dict), f"expected dict shape, got {type(data)}"
    assert data.get("providers"), f"no providers: {data}"
