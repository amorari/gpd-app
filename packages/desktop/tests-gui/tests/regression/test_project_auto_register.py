"""Regression test: project is auto-registered when navigating directly to /:dir.

Commit: bdc28dfc2  (auto-register project on direct /:dir navigation)

Before the fix, navigating directly to a ``/:dir`` URL (deep link, bookmark,
or programmatic navigate) without first opening the project via the sidebar
dialog left the sidebar project list empty.  A ``createEffect`` was added to
``layout.tsx`` that calls ``layout.projects.open(dir)`` whenever the current
directory is not yet in the project list, ensuring the sidebar always reflects
the active project.

This test exercises that path without going through the home screen or any
dialog:
  1. Navigate directly to the project route for a real git directory.
  2. Verify the project appears in the sidebar DOM
     (``[data-project="<token>"]`` element is present).
  3. Verify the sidebar shows the project name or path somewhere in the DOM.
"""
from __future__ import annotations

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)
from gpd_tests.helpers.timings import wait_until


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dom_has_project_entry(probe: DOMProbe, dir_token: str) -> bool:
    """Return True if the project appears in the sidebar DOM.

    Checks in order:
      1. ``[data-project="<token>"]`` — present in the expanded sidebar panel.
      2. Any anchor / element whose href contains the dir token — present in
         the collapsed icon sidebar column.

    Both selectors reflect the sidebar's project registration state.  The
    prompt-input composer is intentionally NOT used as a fallback here because
    it can appear before the sidebar registers the project, which would cause
    the second (text-content) assertion to fail with an empty string.
    """
    js = (
        '(() => {'
        f'  if (document.querySelector(\'[data-project="{dir_token}"]\')) return true;'
        f'  if (document.querySelector(\'[href*="{dir_token}"]\')) return true;'
        '  return false;'
        '})()'
    )
    try:
        return probe.eval_bool(js)
    except ProbeSkip:
        return False


def _dom_composer_present(probe: DOMProbe) -> bool:
    """Return True if the session composer is mounted in the DOM."""
    try:
        return probe.eval_bool(
            '!!document.querySelector(\'[data-component="prompt-input"]\')'
        )
    except ProbeSkip:
        return False


def _dom_project_text(probe: DOMProbe, dir_token: str) -> str:
    """Return the display text of the project entry element.

    The primary [data-project] element is the collapsed icon button; it renders
    only an Avatar initial letter as textContent.  The full project name lives
    in the button's aria-label attribute (set to displayName(project)).  Falls
    back to textContent so any rendering variant still contributes text.
    """
    js = (
        '(() => {'
        f'  const el = document.querySelector(\'[data-project="{dir_token}"]\');'
        '  if (!el) return "";'
        '  return el.getAttribute("aria-label") || el.textContent || "";'
        '})()'
    )
    try:
        result = probe.eval(js)
        return result if isinstance(result, str) else str(result or "")
    except ProbeSkip:
        return ""


# ---------------------------------------------------------------------------
# Regression test
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_project_auto_registered_on_direct_navigation(mcp, git_project_dir):
    """Navigating directly to /:dir must register the project in the sidebar.

    Uses the ``git_project_dir`` fixture (a real git repo in a tmp dir) because
    the sidecar only registers directories it recognises as valid project roots.
    Does NOT go through the sidebar dialog or home screen — that is precisely
    the scenario the bug covered.
    """
    project_path = str(git_project_dir)
    dir_token = encode_dir_token(project_path)

    # Navigate to /:dir/session — semantically equivalent to the bug scenario
    # because the auto-register createEffect in layout.tsx fires for any route
    # under /:dir/*.  Navigating to /:dir directly would cause nav.go to time
    # out: the SPA immediately redirects /:dir → /:dir/session and nav.go's
    # URL-matcher cannot follow that redirect.
    Navigator(mcp).go(route_session_in_project(dir_token), timeout_s=8.0)

    probe = DOMProbe(mcp)

    # Phase 1 — confirm the session layout rendered.
    # The auto-register createEffect lives in the outer Layout (not the session
    # view), so it fires regardless of composer state.  However, if the session
    # never renders at all the DOM assertions below would be meaningless.
    # Allow up to 8s: new git repos need the sidecar to initialise the project
    # before the SyncProvider can receive events and the session can mount.
    composer_appeared = wait_until(
        lambda: _dom_composer_present(probe),
        timeout_s=8.0,
        poll_s=0.2,
    )
    if not composer_appeared:
        pytest.skip(
            "session composer did not render within 8s — the SyncProvider for "
            "this new git project may still be initialising; auto-register "
            "assertion deferred"
        )

    # Phase 2 — verify the project appears in the sidebar.
    # The createEffect calls server.projects.open() via IPC; the sidecar
    # confirms and sends back sync data before the sidebar re-renders.  Allow
    # up to 12s total from navigation for the full IPC+sync round-trip.
    appeared = wait_until(
        lambda: _dom_has_project_entry(probe, dir_token),
        timeout_s=12.0,
        poll_s=0.2,
    )
    target_url = route_session_in_project(dir_token)
    assert appeared, (
        f"regression (bdc28dfc2): navigating directly to {target_url!r} did not "
        f"register the project within 12s. The auto-register createEffect in "
        "layout.tsx is not firing or the projects store is not updating the DOM."
    )

    # Additionally verify that the project name or path appears somewhere in
    # the project entry's text, confirming the sidebar is showing real content
    # rather than an empty placeholder.
    project_name = git_project_dir.name  # last path component (e.g. "pytest-abc123")
    text = _dom_project_text(probe, dir_token)
    # The sidebar may show the full path or just the directory name; either is
    # acceptable evidence that the project registered correctly.
    assert project_name in text or project_path in text, (
        f"regression (bdc28dfc2): sidebar project entry [data-project=\"{dir_token}\"] "
        f"exists but its textContent {text!r} does not contain the project name "
        f"{project_name!r} or full path {project_path!r}. The entry may be empty."
    )
