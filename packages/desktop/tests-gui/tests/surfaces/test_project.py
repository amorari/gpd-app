import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    _adapt_url_for_dev,
    encode_dir_token,
    route_home,
    route_project,
)


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """Create an on-disk directory that GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_proj")
    p = p.resolve()
    (p / "README.md").write_text("# test project\n")
    return str(p)


@pytest.mark.surfaces
def test_project_route_reachable(mcp, prepared_project_path):
    """Project route: URL contains token AND page rendered content.

    URL-only checks can pass for a blank/crashed webview. We also verify
    the document body has rendered elements to catch render failures.
    """
    # Projects register implicitly when a session is created with directory=X.
    # We don't POST /project — that endpoint doesn't exist.
    Navigator(mcp).go(route_project(prepared_project_path), timeout_s=5.0)
    expected_token = encode_dir_token(prepared_project_path)
    url = mcp.current_url()
    assert expected_token in url, f"project token not in url: {url!r}"

    probe = DOMProbe(mcp)
    try:
        rendered = probe.eval_bool(
            '(() => {'
            '  const body = document.body;'
            '  if (!body) return false;'
            '  return body.querySelectorAll("div, main, nav, aside, section, header, footer").length > 0;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert rendered, "project URL loaded but document body contains no rendered elements"


@pytest.mark.surfaces
def test_project_route_navigation_back_to_home_works(mcp, prepared_project_path):
    nav = Navigator(mcp)
    nav.go(route_project(prepared_project_path), timeout_s=5.0)
    nav.go(route_home(), timeout_s=5.0)
    actual = mcp.current_url()
    # Navigator adapts tauri:// to http://localhost:1420 in dev builds;
    # accept either URL as "home".
    assert actual == _adapt_url_for_dev(actual, route_home())


@pytest.mark.surfaces
def test_create_session_for_project_dir_registers_project_via_http(http, prepared_project_path):
    """Backend-only: creating a session with directory= implicitly registers
    the project and the session is retrievable via GET /session.

    This test does NOT exercise the UI — it's an HTTP-contract test that
    guards the implicit project-creation side effect of POST /session.
    Renamed from the misleading ``..._appears_in_session_list`` name which
    suggested a sidebar check.
    """
    session = http.create_session(directory=prepared_project_path)
    session_id = session.get("id") or session.get("sessionID") or session.get("session_id")
    assert session_id, f"create_session returned no id: {session!r}"
    sessions = http.sessions()
    ids = [
        s.get("id") or s.get("sessionID") or s.get("session_id")
        for s in sessions
    ]
    assert session_id in ids, (
        f"session {session_id!r} not found in GET /session: {ids!r}"
    )
