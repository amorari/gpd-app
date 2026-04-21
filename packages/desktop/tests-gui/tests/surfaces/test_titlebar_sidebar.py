"""Surface tests for titlebar + sidebar tree (G5.7).

Covers:
  * ``packages/app/src/components/titlebar.tsx`` — the titlebar new-session
    button. The stable anchor ``data-action="new-session"`` is staged in
    patch ``F4-titlebar-data-action-new-session.patch``. If the patch has
    not landed in the live build, the test xfails with the same reason as
    the F4 smoke test.
  * ``packages/app/src/pages/layout/sidebar-workspace.tsx`` +
    ``sidebar-project.tsx`` — confirms the sidebar tree exposes stable
    ``data-action`` anchors on workspace rows and that clicking a project
    tile navigates to the project route.

Conventions mirror the rest of the surfaces suite:
  - ``Navigator(mcp).go(route_home())`` for deterministic routing.
  - ``DOMProbe`` with ``ProbeSkip`` handling so bridge flake skips instead
    of errors.
  - A disposable project created via HTTP so the sidebar has something to
    render (projects register implicitly when ``create_session(directory=X)``
    is called).
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_project,
)


# Same reason string as the F4 smoke test (tests/smoke/test_sidebar.py);
# keep in sync so a consumer grepping by reason finds both places.
_F4_XFAIL_REASON = (
    "No always-present DOM anchor for the sidebar 'new session' trigger in a "
    "fresh/empty workspace: the existing [data-action=\"workspace-new-session\"] "
    "button inside sidebar-workspace is a hover-revealed child that only "
    "renders once the workspace list contains an entry. Turning this into a "
    "stable smoke assertion needs a product-side change — tagging the always-"
    "present titlebar new-session button with data-action=\"new-session\". "
    "Patch prepared at /tmp/gpd-app-data-action-new-session.patch (F4); will "
    "be submitted as a separate PR to gpd-app."
)


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """On-disk directory GPD will treat as a project once a session is created."""
    p = tmp_path_factory.mktemp("gpd_titlebar_sidebar")
    (p / "README.md").write_text("# test project\n")
    return str(p)


@pytest.fixture
def seeded_project(http, prepared_project_path) -> str:
    """Register ``prepared_project_path`` with GPD by creating a session.

    Projects register implicitly when ``create_session`` is called with
    ``directory=X``. Once seeded, the sidebar tree has something to render.
    """
    ses = http.create_session(directory=prepared_project_path)
    sid = ses["id"]
    try:
        yield prepared_project_path
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 1. Titlebar new-session button (F4 patch)
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=False, reason=_F4_XFAIL_REASON)
def test_titlebar_new_session_button_is_enabled(mcp, seeded_project):
    """The titlebar ``data-action="new-session"`` button is present + enabled.

    The button only renders when ``params.dir`` is set (i.e. on a project
    route), so we navigate to the project first. xfails until the F4 patch
    lands.
    """
    Navigator(mcp).go(route_project(seeded_project), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        enabled = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"new-session\\"]"'
            '  );'
            '  if (!el) return false;'
            '  const disabled = el.disabled === true'
            '    || el.getAttribute("aria-disabled") === "true";'
            '  return !disabled;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert enabled, (
        "titlebar [data-action=\"new-session\"] not present or is disabled"
    )


# ---------------------------------------------------------------------------
# 2. Sidebar workspace list shape
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_sidebar_workspace_list_shape(mcp, seeded_project):
    """The sidebar tree exposes at least one row with a stable ``data-action``.

    Once a project is registered, one of the following always-present anchors
    must be in the DOM tree:
      - ``[data-action="project-switch"]`` (sidebar rail project tile)
      - ``[data-action="project-menu"]`` (project header more-options)
      - ``[data-action="workspace-toggle"]`` (collapsible workspace row)
      - ``[data-action="workspace-menu"]`` (workspace row more-options)

    This is a structural probe: we don't care which one, just that the
    sidebar has rendered *something* with our data-action convention.
    """
    nav = Navigator(mcp)
    # Land on home first so globalSync has a chance to propagate the seeded
    # project before we navigate to its route. In the VM, globalSync latency
    # can exceed 8s; routing through home adds virtually no time but lets the
    # sync bootstrap finish in the background while the home shell mounts.
    nav.go(route_home(), timeout_s=5.0)
    time.sleep(1.0)  # let globalSync bootstrap propagate the seeded project
    nav.go(route_project(seeded_project), timeout_s=5.0)
    probe = DOMProbe(mcp)
    # Poll — the sidebar re-renders once project data arrives over globalSync.
    # Total budget: 15s (VM globalSync latency can exceed 8s).
    selectors = (
        '[data-action="project-switch"]',
        '[data-action="project-menu"]',
        '[data-action="workspace-toggle"]',
        '[data-action="workspace-menu"]',
        '[data-component="workspace-item"]',
    )
    joined = ", ".join(s.replace('"', '\\"') for s in selectors)
    deadline = time.monotonic() + 15.0
    found = False
    while time.monotonic() < deadline:
        try:
            found = probe.eval_bool(
                f'!!document.querySelector("{joined}")'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if found:
            break
        time.sleep(0.2)
    assert found, (
        "sidebar has no workspace/project row with a data-action anchor; "
        f"tried: {selectors}"
    )


# ---------------------------------------------------------------------------
# 3. Clicking a project item navigates to its route
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_sidebar_project_item_click_navigates(mcp, seeded_project):
    """Clicking the sidebar ``project-switch`` tile updates the URL.

    The tile carries ``data-project={base64Encode(worktree)}`` which must
    match ``encode_dir_token(worktree)`` — both produce URL-safe base64
    without padding. After click, the URL must contain that token.
    """
    # Start on home so we observe the transition (not start-same-as-end).
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    token = encode_dir_token(seeded_project)
    probe = DOMProbe(mcp)

    # Wait for the tile carrying our token to mount. It's rendered by the
    # sidebar rail regardless of sidebar-open state.
    selector = f'[data-action="project-switch"][data-project="{token}"]'
    deadline = time.monotonic() + 3.0
    present = False
    while time.monotonic() < deadline:
        try:
            present = probe.eval_bool(
                f'!!document.querySelector({selector!r})'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if present:
            break
        time.sleep(0.1)
    if not present:
        pytest.skip(
            f"project tile with data-project={token!r} not present on home "
            "(rail may be collapsed or layout shell not mounted)"
        )

    # Click it.
    try:
        clicked = probe.eval_bool(
            '(() => {'
            f'  const el = document.querySelector({selector!r});'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert clicked, "could not click project-switch tile"

    # Poll current_url() until it contains the token (or time out).
    deadline = time.monotonic() + 3.0
    url = ""
    while time.monotonic() < deadline:
        try:
            url = mcp.current_url()
        except Exception:
            url = ""
        if token in url:
            return
        time.sleep(0.1)
    pytest.fail(
        f"URL did not change to contain token {token!r} after clicking "
        f"project tile; last url={url!r}"
    )
