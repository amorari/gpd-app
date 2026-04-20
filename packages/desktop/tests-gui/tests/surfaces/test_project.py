import pytest

from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_project,
)


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """Create an on-disk directory that GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_proj")
    (p / "README.md").write_text("# test project\n")
    return str(p)


@pytest.mark.surfaces
def test_project_route_reachable(mcp, http, prepared_project_path):
    # Register the project via the sidecar, ignore if endpoint differs.
    try:
        http._client.post("/project", json={"path": prepared_project_path})
    except Exception:
        pass  # route may work without explicit registration
    Navigator(mcp).go(route_project(prepared_project_path), timeout_s=5.0)
    expected_token = encode_dir_token(prepared_project_path)
    url = mcp.current_url()
    assert expected_token in url, f"project token not in url: {url!r}"


@pytest.mark.surfaces
def test_project_route_navigation_back_to_home_works(mcp, prepared_project_path):
    nav = Navigator(mcp)
    nav.go(route_project(prepared_project_path), timeout_s=5.0)
    nav.go(route_home(), timeout_s=5.0)
    assert mcp.current_url() == route_home()
