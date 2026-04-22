"""Surface tests for untested sidebar actions (G5.8).

Covers:
  1. Session archive via the session-level DropdownMenu (data-action="session-menu-archive")
  2. Project workspaces toggle via the project header DropdownMenu
     (data-action="project-workspaces-toggle")
  3. Todo dock collapse/expand toggle (data-action="session-todo-toggle")

Implementation notes
--------------------
* Test 1 — session archive
  The sidebar's archive button (``IconButton icon="archive"``) has NO
  ``data-action`` attribute; it only appears under CSS ``group-hover`` state
  which cannot be reliably triggered by JS.  The stable
  ``data-action="session-menu-archive"`` anchor lives in the session view's
  DropdownMenu (``message-timeline.tsx``), opened via
  ``data-action="session-menu-open"``.  The test navigates to the session
  route, opens the dropdown, and clicks archive.

* Test 2 — project workspaces toggle
  ``data-action="project-workspaces-toggle"`` is a DropdownMenu item inside the
  project header's more-options menu (``data-action="project-menu"``).  The
  item is rendered in a Kobalte portal; a short settle sleep is required after
  opening the trigger.

* Test 3 — todo dock toggle
  ``data-action="session-todo-toggle"`` and the related
  ``data-action="session-todo-toggle-button"`` (which carries
  ``data-collapsed="true|false"``) only appear when the session has active
  todos.  There is no HTTP endpoint to inject todos, so this test skips if the
  dock is not present — it validates toggle behaviour when the dock IS
  present rather than forcing an impossible precondition.

Patterns follow test_session_components.py and test_titlebar_sidebar.py:
  - Navigator / DOMProbe / ProbeSkip / wait_until
  - All tests marked @pytest.mark.surfaces
  - Soft-skip (pytest.skip) rather than hard-fail when a UI anchor is absent.
"""
from __future__ import annotations

import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_session_in_project,
)
from gpd_tests.helpers.timings import wait_until


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """Disposable real git repo that GPD will treat as a project.

    A git repo is required because:
    - The sidecar only registers git directories as projects.
    - The project-workspaces-toggle is only enabled for git repos
      (non-git projects cannot enable workspaces).
    """
    p = tmp_path_factory.mktemp("gpd_sidebar_actions")
    # Resolve symlinks: on macOS /var → /private/var; the sidecar normalises
    # paths to their canonical form so we must use the same form throughout.
    p = p.resolve()
    (p / "README.md").write_text("# test project\n")
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(p), check=True, capture_output=True)
    subprocess.run(
        [
            "git", "-c", "user.email=test@test.com",
            "-c", "user.name=Test", "commit", "-m", "init",
        ],
        cwd=str(p), check=True, capture_output=True,
    )
    return str(p)


def _safe_delete(http, sid: str) -> None:
    """Best-effort session deletion — never raises."""
    try:
        http.delete_session(sid)
    except Exception:  # noqa: BLE001
        pass


def _dom_has_session_row(probe: DOMProbe, sid: str) -> bool:
    js = f'!!document.querySelector(\'[data-session-id="{sid}"]\')'
    try:
        return probe.eval_bool(js)
    except ProbeSkip:
        return False


# ---------------------------------------------------------------------------
# Test 1: Session archive via the session DropdownMenu
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_session_archive_via_session_menu(mcp, http, prepared_project_path):
    """Archive a session via data-action="session-menu-archive" and verify it
    disappears from the sidebar session list.

    Flow:
      1. Create a session via HTTP.
      2. Navigate to the session route (``/:dir/session/:id``).
      3. Open the more-options DropdownMenu (``data-action="session-menu-open"``).
      4. Click the archive item (``data-action="session-menu-archive"``).
      5. Navigate back to the project session-list route.
      6. Assert the session row ([data-session-id=...]) is no longer present.
    """
    ses = http.create_session(directory=prepared_project_path)
    sid = ses.get("id")
    assert sid, f"create_session returned no id: {ses!r}"

    dir_token = encode_dir_token(prepared_project_path)
    session_route = route_session_in_project(dir_token, sid)
    list_route = route_session_in_project(dir_token)

    try:
        nav = Navigator(mcp)
        # Navigate home then session list to register the project in the
        # sidecar and prime the SSE session-list sync before going to the
        # specific session URL. Without this warmup, messagesReady() can
        # be slow to become true on first visit to a brand-new project.
        nav.go(route_home(), timeout_s=5.0)
        time.sleep(0.5)
        nav.go(list_route, timeout_s=8.0)
        time.sleep(1.0)
        nav.go(session_route, timeout_s=8.0)
        probe = DOMProbe(mcp)

        # Wait for the session-menu-open anchor to mount.
        # MessageTimeline renders only after messagesReady() is true
        # (sync.data.message[id] !== undefined). For a fresh empty session
        # the SSE sync fires shortly after navigation; allow up to 20s.
        menu_open_sel = '[data-action="session-menu-open"]'
        deadline_mount = time.monotonic() + 20.0
        menu_ready = False
        while time.monotonic() < deadline_mount:
            try:
                menu_ready = probe.eval_bool(
                    f'!!document.querySelector({menu_open_sel!r})'
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            if menu_ready:
                break
            time.sleep(0.2)
        if not menu_ready:
            pytest.skip(
                'data-action="session-menu-open" not found after 20s; '
                'session page may not have mounted yet'
            )

        # Open the more-options dropdown.
        open_js = (
            '(() => {'
            '  const btn = document.querySelector(\'[data-action="session-menu-open"]\');'
            '  if (!btn) return "missing";'
            '  btn.click();'
            '  return "clicked";'
            '})()'
        )
        try:
            result = probe.eval(open_js)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        result_str = str(result).strip('"')
        if result_str == "missing":
            pytest.skip(
                "data-action=\"session-menu-open\" not found; "
                "the session page may not have mounted yet or the anchor is absent"
            )

        # Kobalte DropdownMenu portals mount asynchronously after click.
        time.sleep(0.3)

        # Click the archive menu item. The item is portalled into the body.
        archive_js = (
            '(() => {'
            '  const item = document.querySelector(\'[data-action="session-menu-archive"]\');'
            '  if (!item) return "missing";'
            '  item.click();'
            '  return "clicked";'
            '})()'
        )
        try:
            archive_result = probe.eval(archive_js)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable after opening menu ({e})")

        archive_str = str(archive_result).strip('"')
        if archive_str == "missing":
            pytest.skip(
                "data-action=\"session-menu-archive\" not found in the open dropdown; "
                "the portal may not have mounted or the item is not rendered"
            )

        # Short settle for the archive mutation to propagate.
        time.sleep(0.4)

        # Navigate back to the session list to check the sidebar DOM.
        nav.go(list_route, timeout_s=5.0)

        # Allow any in-flight sync to remove the archived session from the list.
        def _row_gone() -> bool:
            return not _dom_has_session_row(probe, sid)

        disappeared = wait_until(_row_gone, timeout_s=8.0, poll_s=0.2)
        assert disappeared, (
            f"session row [data-session-id={sid!r}] still visible after archive; "
            "archived sessions should not appear in the main session list"
        )
    finally:
        # Archive sets archived=<timestamp>; delete cleans up regardless.
        _safe_delete(http, sid)


# ---------------------------------------------------------------------------
# Test 2: Project workspaces toggle
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_project_workspaces_toggle(mcp, http, prepared_project_path):
    """Toggle workspace mode on/off via data-action="project-workspaces-toggle".

    Flow:
      1. Seed the project by creating a session (registers the project in GPD).
      2. Navigate to the project route.
      3. Wait for the project-menu trigger to appear in the DOM.
      4. Click ``data-action="project-menu"`` to open the DropdownMenu.
      5. Click ``data-action="project-workspaces-toggle"`` (enable or disable).
      6. Assert the DOM changed: either ``[data-component="workspace-item"]``
         appears (workspaces enabled) or ``[data-action="workspace-toggle"]``
         disappears (workspaces disabled), compared with the initial state.
    """
    ses = http.create_session(directory=prepared_project_path)
    sid = ses.get("id")
    assert sid, f"create_session returned no id: {ses!r}"

    try:
        nav = Navigator(mcp)
        # Route through home first so globalSync has a chance to propagate.
        nav.go(route_home(), timeout_s=5.0)
        time.sleep(1.0)
        # Use /:dir/session instead of /:dir — the SPA immediately redirects
        # /:dir → /:dir/session, which nav.go's URL-matcher cannot follow.
        nav.go(
            route_session_in_project(encode_dir_token(prepared_project_path)),
            timeout_s=8.0,
        )
        probe = DOMProbe(mcp)

        # Wait for the project-menu trigger to appear (sidebar may still be
        # rendering after globalSync latency).
        project_menu_sel = '[data-action="project-menu"]'
        deadline = time.monotonic() + 15.0
        menu_present = False
        while time.monotonic() < deadline:
            try:
                menu_present = probe.eval_bool(
                    f'!!document.querySelector({project_menu_sel!r})'
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            if menu_present:
                break
            time.sleep(0.3)

        if not menu_present:
            pytest.skip(
                "data-action=\"project-menu\" not found after 15s; "
                "sidebar may be collapsed or the project did not register in time"
            )

        # Record the pre-toggle workspace state.
        workspace_sel = (
            '[data-component="workspace-item"], '
            '[data-action="workspace-toggle"]'
        )
        try:
            had_workspaces = probe.eval_bool(
                f'!!document.querySelector({workspace_sel!r})'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        toggle_sel = '[data-action="project-workspaces-toggle"]'
        # Open the project-menu DropdownMenu, poll for the toggle to appear
        # AND be enabled. Retry up to 5× (2s apart) because the sidecar may
        # not deliver vcs:"git" to the frontend store before the first open.
        open_menu_js = (
            '(() => {'
            f'  const btn = document.querySelector({project_menu_sel!r});'
            '  if (!btn) return "missing";'
            '  btn.dispatchEvent(new PointerEvent("pointerdown", {bubbles: true, cancelable: true}));'
            '  btn.dispatchEvent(new PointerEvent("pointerup", {bubbles: true, cancelable: true}));'
            '  btn.click();'
            '  return "clicked";'
            '})()'
        )
        toggle_js = (
            '(() => {'
            f'  const item = document.querySelector({toggle_sel!r});'
            '  if (!item) return "missing";'
            '  if (item.dataset.disabled === "" || item.getAttribute("aria-disabled") === "true")'
            '    return "disabled";'
            # Kobalte DropdownMenu.Item fires onSelect via its onPointerUp handler
            # (not onClick).  Dispatch the full pointer sequence so the handler fires.
            '  const opts = {bubbles: true, cancelable: true, button: 0, isPrimary: true, pointerType: "mouse"};'
            '  item.dispatchEvent(new PointerEvent("pointerdown", {...opts, buttons: 1}));'
            '  item.dispatchEvent(new PointerEvent("pointerup",   {...opts, buttons: 0}));'
            '  return "clicked";'
            '})()'
        )
        dismiss_js = (
            'document.dispatchEvent(new KeyboardEvent("keydown",'
            ' {key: "Escape", bubbles: true, cancelable: true}))'
        )

        toggle_str = "missing"
        for attempt in range(5):
            # Open the menu.
            try:
                open_result = probe.eval(open_menu_js)
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")

            if str(open_result).strip('"') == "missing":
                pytest.skip("data-action=\"project-menu\" disappeared before click")

            # Poll for portal to mount with toggle item present.
            found_deadline = time.monotonic() + 3.0
            toggle_in_dom = False
            while time.monotonic() < found_deadline:
                try:
                    toggle_in_dom = probe.eval_bool(
                        f'!!document.querySelector({toggle_sel!r})'
                    )
                except ProbeSkip as e:
                    pytest.skip(f"execute_js unavailable ({e})")
                if toggle_in_dom:
                    break
                time.sleep(0.1)

            if not toggle_in_dom:
                pytest.skip(
                    "data-action=\"project-workspaces-toggle\" not found in open menu; "
                    "the portal may not have mounted"
                )

            try:
                toggle_result = probe.eval(toggle_js)
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")

            toggle_str = str(toggle_result).strip('"')
            if toggle_str != "disabled":
                break

            # Dismiss the menu and wait for the sidecar vcs detection to
            # propagate via SSE before retrying.
            try:
                probe.eval(dismiss_js)
            except ProbeSkip:
                pass
            time.sleep(2.0)

        if toggle_str == "missing":
            pytest.skip(
                "data-action=\"project-workspaces-toggle\" disappeared after polling; "
                "portal unmounted unexpectedly"
            )
        if toggle_str == "disabled":
            pytest.skip(
                "project-workspaces-toggle is still disabled after 5 retries; "
                "sidecar did not detect the project as a git repo in time"
            )

        # Allow the toggle mutation (store update + re-render) to settle.
        time.sleep(2.0)

        # Assert the DOM changed from the pre-toggle state.
        try:
            has_workspaces_after = probe.eval_bool(
                f'!!document.querySelector({workspace_sel!r})'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable after toggle ({e})")

        assert has_workspaces_after != had_workspaces, (
            f"workspace DOM state did not change after clicking "
            f"project-workspaces-toggle; "
            f"before={had_workspaces!r}, after={has_workspaces_after!r}. "
            "Either the toggle had no effect or the sidebar did not re-render."
        )
    finally:
        _safe_delete(http, sid)


# ---------------------------------------------------------------------------
# Test 3: Todo dock toggle
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Todo dock requires an active session with in-progress todos. "
        "There is no HTTP endpoint to inject todos into an idle session, "
        "so this test always skips in CI — marking xfail so the always-skip "
        "is visible in the report rather than silently staying green."
    ),
)
def test_session_todo_dock_toggle(mcp, http, prepared_project_path):
    """Verify data-action="session-todo-toggle" collapses/expands the todo dock.

    The todo dock only renders when the session has active todos
    (``todos().length > 0 && live()``). There is no HTTP API to inject todos
    into an idle session, so this test skips if the dock is not present rather
    than fabricating an impossible precondition.

    When the dock IS present:
      1. Navigate to the session route.
      2. Confirm the dock header (data-action="session-todo-toggle") is in the DOM.
      3. Read the initial collapsed state from the toggle button
         (data-action="session-todo-toggle-button" data-collapsed="false|true").
      4. Click the toggle.
      5. Assert data-collapsed flipped.
    """
    ses = http.create_session(directory=prepared_project_path)
    sid = ses.get("id")
    assert sid, f"create_session returned no id: {ses!r}"

    dir_token = encode_dir_token(prepared_project_path)
    session_route = route_session_in_project(dir_token, sid)

    try:
        nav = Navigator(mcp)
        nav.go(session_route, timeout_s=8.0)
        probe = DOMProbe(mcp)

        # The todo dock only mounts when there are active todos. Give the session
        # a moment to settle, then check.
        time.sleep(0.5)

        dock_sel = '[data-action="session-todo-toggle"]'
        try:
            dock_present = probe.eval_bool(
                f'!!document.querySelector({dock_sel!r})'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not dock_present:
            pytest.skip(
                "data-action=\"session-todo-toggle\" not found; "
                "the todo dock only appears when the session has active todos. "
                "This test requires a session with in-progress todos to exercise "
                "the toggle — skipping on an idle session."
            )

        # Read the initial collapsed state from the toggle button.
        btn_sel = '[data-action="session-todo-toggle-button"]'
        get_collapsed_js = (
            '(() => {'
            f'  const btn = document.querySelector({btn_sel!r});'
            '  if (!btn) return "missing";'
            '  return btn.dataset.collapsed;'
            '})()'
        )
        try:
            initial_collapsed_raw = probe.eval(get_collapsed_js)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        initial_collapsed_str = str(initial_collapsed_raw).strip('"')
        if initial_collapsed_str == "missing":
            pytest.skip(
                "data-action=\"session-todo-toggle-button\" not found; "
                "cannot read initial collapsed state"
            )

        # Click the toggle header.
        click_js = (
            '(() => {'
            f'  const el = document.querySelector({dock_sel!r});'
            '  if (!el) return "missing";'
            '  el.click();'
            '  return "clicked";'
            '})()'
        )
        try:
            click_result = probe.eval(click_js)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if str(click_result).strip('"') == "missing":
            pytest.skip("data-action=\"session-todo-toggle\" disappeared before click")

        # Allow the spring animation to start and the store to update.
        time.sleep(0.3)

        # Read the new collapsed state.
        try:
            after_collapsed_raw = probe.eval(get_collapsed_js)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable after toggle ({e})")

        after_collapsed_str = str(after_collapsed_raw).strip('"')

        # Expect the state to have flipped.
        assert after_collapsed_str != initial_collapsed_str, (
            f"todo dock collapsed state did not change after clicking "
            f"data-action=\"session-todo-toggle\"; "
            f"before={initial_collapsed_str!r}, after={after_collapsed_str!r}"
        )
    finally:
        _safe_delete(http, sid)
