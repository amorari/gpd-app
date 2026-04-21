import pytest


@pytest.mark.smoke
def test_gpd_process_is_running(app_state):
    assert app_state.is_running()


@pytest.mark.smoke
def test_sidecar_is_healthy(http):
    health = http.health()
    assert health.get("healthy") is True
    assert isinstance(health.get("version"), str)
