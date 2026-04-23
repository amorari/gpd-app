import pytest


@pytest.mark.smoke
@pytest.mark.real_backend
def test_providers_non_empty(http, gpd_key):
    data = http.providers()
    assert isinstance(data, dict), f"expected dict shape, got {type(data)}"
    assert data.get("providers"), f"no providers: {data}"
