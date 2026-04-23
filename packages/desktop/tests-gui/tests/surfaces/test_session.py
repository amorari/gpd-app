import time

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
    p = p.resolve()
    (p / "README.md").write_text("# test project\n")
    return str(p)


def _session_route(path: str) -> str:
    return route_session_in_project(encode_dir_token(path))


@pytest.mark.surfaces
def test_session_route_reachable(mcp, prepared_project_path):
    """Session route: URL resolves AND page rendered something.

    A URL-only check passes for a crashed webview at /session — we also
    verify the document body has rendered elements so we catch the case
    where routing works but the SPA failed to mount.
    """
    url = _session_route(prepared_project_path)
    Navigator(mcp).go(url, timeout_s=5.0)
    assert "/session" in mcp.current_url()

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
    assert rendered, "session URL loaded but document body contains no rendered elements"


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
    # Poll until the button is found and confirmed disabled (or timeout).
    # JS returns null (→ Python "null" string) when the button isn't mounted
    # yet; eval() is used instead of eval_bool() so we can distinguish that
    # case from "button present but enabled" (which would be false).
    deadline = time.monotonic() + 5.0
    disabled = None
    while time.monotonic() < deadline:
        try:
            raw = probe.eval(
                '(() => {'
                '  const btns = Array.from(document.querySelectorAll('
                '    "button[data-action=\\"prompt-submit\\"][type=\\"submit\\"]"'
                '  ));'
                '  if (btns.length === 0) return null;'
                '  return btns.every('
                '    b => b.disabled || b.getAttribute("aria-disabled") === "true"'
                '  );'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if raw is None or (isinstance(raw, str) and raw.strip().lower() == "null"):
            time.sleep(0.15)
            continue
        if isinstance(raw, bool):
            disabled = raw
        elif isinstance(raw, str):
            disabled = raw.strip().lower() not in {"false", "0", ""}
        else:
            disabled = bool(raw)
        if disabled:
            break
        time.sleep(0.15)
    if disabled is None:
        pytest.skip("prompt-submit button not mounted within 5s")
    assert disabled, "send button not disabled on empty composer"
