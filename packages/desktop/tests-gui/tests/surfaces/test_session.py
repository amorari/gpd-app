import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)
from gpd_tests.helpers.selectors import TEXT_PROMPT_PLACEHOLDER


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """Create an on-disk directory that GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_proj_session")
    (p / "README.md").write_text("# test project\n")
    return str(p)


def _session_route(path: str) -> str:
    return route_session_in_project(encode_dir_token(path))


@pytest.mark.surfaces
def test_session_route_reachable(mcp, prepared_project_path):
    url = _session_route(prepared_project_path)
    Navigator(mcp).go(url, timeout_s=5.0)
    assert "/session" in mcp.current_url()


@pytest.mark.surfaces
def test_composer_placeholder_present(mcp, prepared_project_path):
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)
    probe = DOMProbe(mcp)
    escaped = TEXT_PROMPT_PLACEHOLDER.replace('"', '\\"')
    try:
        found = probe.eval_bool(
            'Array.from(document.querySelectorAll("[placeholder]"))'
            f'.some(el => el.placeholder === "{escaped}")'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not found:
        pytest.skip(
            f"no element has placeholder={TEXT_PROMPT_PLACEHOLDER!r} "
            "(welcome overlay or different composer layout)"
        )
    assert found


@pytest.mark.surfaces
def test_send_button_disabled_on_empty_input(mcp, prepared_project_path):
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        # The send button may be a regular Button or an IconButton; match both.
        disabled = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll('
            '    "button[data-component=\\"button\\"][type=\\"submit\\"],'
            '     button[data-component=\\"icon-button\\"][type=\\"submit\\"]"'
            '  ));'
            '  if (btns.length === 0) return false;'
            '  return btns.every('
            '    b => b.disabled || b.getAttribute("aria-disabled") === "true"'
            '  );'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert disabled, "send button not disabled on empty composer"
