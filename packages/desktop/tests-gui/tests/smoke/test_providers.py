import os

import pytest


@pytest.mark.smoke
@pytest.mark.real_backend
@pytest.mark.skipif(
    not (lambda p: p.exists() and __import__("json").loads(p.read_text()).get("gpd",{}).get("key",""))(__import__("pathlib").Path.home()/".local/share/opencode/auth.json"),
    reason="GPD key not found in auth.json",
)
def test_providers_non_empty(http):
    data = http.providers()
    assert isinstance(data, dict), f"expected dict shape, got {type(data)}"
    assert data.get("providers"), f"no providers: {data}"
