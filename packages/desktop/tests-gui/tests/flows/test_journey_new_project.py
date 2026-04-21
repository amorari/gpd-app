"""Phase G6.2 end-to-end journey: create a new project via the open-or-create dialog.

Journey 2 prefix from docs/coverage-expansion/inventory/user-journeys.md —
"New project" path only (chat + abort are covered by other G6 tasks).

Steps exercised:
  1. Open the DialogOpenOrCreateProject dialog from home.
  2. Switch the dialog into "create" mode.
  3. Enter a project name.
  4. Stub / bypass the native directory picker to set the parent to tmp_path.
  5. Click the primary submit button.
  6. Poll current_url until it matches the project-home URL (base64(root)).
  7. Assert the created project is visible in the sidebar / workspace list via
     the HTTP /project route (authoritative source of truth).
  8. Clean up by calling http.delete_project(...) in finally (more reliable
     than the UI confirmation flow per G3.3 notes).

Why xfail (as of 2026-04-20):
  The DialogOpenOrCreateProject has no `data-action` anchors — the only
  trigger paths are visible text (i18n-fragile) or Kobalte component tags
  (which don't distinguish Create from Open tiles). Staged patch:
  docs/gpd-app-patches/G6-openorcreate-data-actions.patch. The parent-picker
  additionally invokes a native OS dialog that MCP cannot automate; even
  with anchors, a test-only override for platform.openDirectoryPickerDialog
  is required. Both requirements are noted in the patch's trailing comment.

Once the patch lands and the native-picker stub is available (or we fall
back to driving the create path via the `project_fs` Tauri command and then
verifying the sidebar list), drop the xfail.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, encode_dir_token, route_home


_OPEN_OR_CREATE_BUTTON_RE = r"/open.*create|create.*project|new project/i"


def _click_home_open_or_create(probe: DOMProbe) -> bool:
    """Click the home 'Open Existing / Create New' button. Returns True if found."""
    return probe.eval_bool(
        '(() => {'
        '  const btns = Array.from(document.querySelectorAll("button"));'
        '  const btn = btns.find('
        f'    b => {_OPEN_OR_CREATE_BUTTON_RE}.test(b.innerText)'
        '  );'
        '  if (!btn) return false;'
        '  btn.click();'
        '  return true;'
        '})()'
    )


def _wait_for_dialog(probe: DOMProbe, *, timeout_s: float = 3.0) -> bool:
    """Wait for the DialogOpenOrCreateProject to render by looking for its title text."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            found = probe.eval_bool(
                '(() => {'
                '  const txt = document.body ? document.body.innerText : "";'
                '  return /open or create/i.test(txt) || '
                '         /open existing folder/i.test(txt) || '
                '         /create new folder/i.test(txt);'
                '})()'
            )
        except ProbeSkip:
            raise
        if found:
            return True
        time.sleep(0.1)
    return False


def _click_create_tile(probe: DOMProbe) -> bool:
    """Click the 'Create New Folder' tile in the dialog."""
    # Preferred: data-action selector (requires G6-openorcreate-data-actions.patch).
    clicked = probe.eval_bool(
        '(() => {'
        '  const el = document.querySelector('
        '    "[data-action=\\"openorcreate-create\\"]"'
        '  );'
        '  if (!el) return false;'
        '  el.click();'
        '  return true;'
        '})()'
    )
    if clicked:
        return True
    # Fallback: text-match the tile by visible title. i18n-fragile but keeps
    # the test from hard-crashing before the patch lands.
    return probe.eval_bool(
        '(() => {'
        '  const tiles = Array.from(document.querySelectorAll("button"));'
        '  const tile = tiles.find(b => /create new folder/i.test(b.innerText));'
        '  if (!tile) return false;'
        '  tile.click();'
        '  return true;'
        '})()'
    )


def _set_name_input(probe: DOMProbe, name: str) -> bool:
    """Type the project name into the TextField. Dispatches input event for Solid."""
    script = (
        '(() => {'
        '  const el = document.querySelector('
        '    "[data-action=\\"openorcreate-name-input\\"] input, '
        '     [data-action=\\"openorcreate-name-input\\"]"'
        '  );'
        '  const input = el && (el.tagName === "INPUT" ? el : el.querySelector("input"));'
        '  if (!input) return false;'
        f'  input.value = {name!r};'
        '  input.dispatchEvent(new Event("input", { bubbles: true }));'
        '  input.dispatchEvent(new Event("change", { bubbles: true }));'
        '  return true;'
        '})()'
    )
    if probe.eval_bool(script):
        return True
    # Fallback: find by placeholder text (i18n key home.combinedPicker.create.namePlaceholder).
    fallback = (
        '(() => {'
        '  const inputs = Array.from(document.querySelectorAll("input"));'
        '  const input = inputs.find(i => /curvature-flow|project name/i.test('
        '    (i.placeholder || "") + " " + (i.getAttribute("aria-label") || "")'
        '  ));'
        '  if (!input) return false;'
        f'  input.value = {name!r};'
        '  input.dispatchEvent(new Event("input", { bubbles: true }));'
        '  input.dispatchEvent(new Event("change", { bubbles: true }));'
        '  return true;'
        '})()'
    )
    return probe.eval_bool(fallback)


def _stub_native_picker_and_set_parent(probe: DOMProbe, parent_path: str) -> bool:
    """Override platform.openDirectoryPickerDialog to return ``parent_path`` once,
    then click the parent-picker button so the Solid signal updates.

    This is a test-only override; if the product does not expose
    ``window.__OPENCODE__.platform`` (or an equivalent surface), this step will
    fail and the test falls through to xfail.
    """
    override_script = (
        '(() => {'
        f'  const ret = {parent_path!r};'
        '  const gbl = window.__OPENCODE__ || window.__opencode__ || null;'
        '  if (gbl && gbl.platform && typeof gbl.platform === "object") {'
        '    gbl.platform.openDirectoryPickerDialog = async () => ret;'
        '    return true;'
        '  }'
        '  return false;'
        '})()'
    )
    stubbed = probe.eval_bool(override_script)
    if not stubbed:
        # No override hook available yet. Test will proceed and likely fail
        # waiting for parent to be set — caller handles the xfail.
        return False
    # Click the parent-picker button.
    return probe.eval_bool(
        '(() => {'
        '  const el = document.querySelector('
        '    "[data-action=\\"openorcreate-parent-button\\"]"'
        '  );'
        '  if (!el) return false;'
        '  el.click();'
        '  return true;'
        '})()'
    )


def _click_submit(probe: DOMProbe) -> bool:
    """Click the 'Create and open' submit button."""
    return probe.eval_bool(
        '(() => {'
        '  const el = document.querySelector('
        '    "[data-action=\\"openorcreate-submit\\"]"'
        '  );'
        '  if (!el || el.disabled) return false;'
        '  el.click();'
        '  return true;'
        '})()'
    )


def _wait_for_project_url(mcp, expected_token: str, *, timeout_s: float = 8.0) -> bool:
    """Poll current_url until the path segment equals ``expected_token``."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            url = mcp.current_url()
        except Exception:
            url = ""
        # The URL shape is ``tauri://localhost/<token>[/...]``. We only care
        # that the first path segment matches.
        if f"/{expected_token}" in url:
            return True
        time.sleep(0.1)
    return False


@pytest.mark.flows
@pytest.mark.surfaces
@pytest.mark.xfail(
    reason=(
        "pending G6-openorcreate-data-actions.patch (no data-action anchors "
        "on DialogOpenOrCreateProject) and a test-only override for "
        "platform.openDirectoryPickerDialog (native picker is not MCP-automatable)"
    ),
    strict=False,
)
def test_journey_new_project(mcp, http, tmp_path):
    """End-to-end: open dialog -> create project via UI -> land on home -> verify in list -> delete."""
    # Pick a unique sub-path so the finally cleanup is deterministic even if
    # the test reruns in the same session.
    parent_dir = tmp_path / "g62-parent"
    parent_dir.mkdir(parents=True, exist_ok=True)
    project_name = "g62-new-project"
    expected_worktree = parent_dir / project_name

    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)

    created_project_id: str | None = None
    try:
        # 1. Open the dialog.
        try:
            if not _click_home_open_or_create(probe):
                pytest.skip("no 'Open Existing / Create New' button found on home")
            if not _wait_for_dialog(probe):
                pytest.fail("open-or-create dialog did not render within deadline")

            # 2. Switch to create mode.
            if not _click_create_tile(probe):
                pytest.fail("'Create New Folder' tile not clickable")

            # Wait for the name input to render in the create panel.
            deadline = time.monotonic() + 2.0
            has_input = False
            while time.monotonic() < deadline:
                try:
                    has_input = probe.eval_bool(
                        '(() => !!document.querySelector('
                        '"[data-action=\\"openorcreate-name-input\\"] input, '
                        ' [data-action=\\"openorcreate-name-input\\"] input, '
                        ' input[placeholder*=curvature-flow]"'
                        '))()'
                    )
                except ProbeSkip as e:
                    pytest.skip(f"execute_js unavailable ({e})")
                if has_input:
                    break
                time.sleep(0.1)
            if not has_input:
                pytest.fail("name input did not appear after mode switch")

            # 3. Enter the project name.
            if not _set_name_input(probe, project_name):
                pytest.fail("could not type into project name input")

            # 4. Stub the native picker and click the parent-picker button.
            if not _stub_native_picker_and_set_parent(probe, str(parent_dir)):
                pytest.xfail(
                    "window.__OPENCODE__.platform override hook not available — "
                    "native directory picker cannot be driven via MCP; "
                    "see G6-openorcreate-data-actions.patch trailing notes"
                )

            # Wait for the submit button to enable (Solid signal update after
            # parent() + name() are both set).
            deadline = time.monotonic() + 2.0
            enabled = False
            while time.monotonic() < deadline:
                try:
                    enabled = probe.eval_bool(
                        '(() => {'
                        '  const el = document.querySelector('
                        '    "[data-action=\\"openorcreate-submit\\"]"'
                        '  );'
                        '  return !!el && !el.disabled;'
                        '})()'
                    )
                except ProbeSkip as e:
                    pytest.skip(f"execute_js unavailable ({e})")
                if enabled:
                    break
                time.sleep(0.1)
            if not enabled:
                pytest.fail("submit button never became enabled")

            # 5. Click submit.
            if not _click_submit(probe):
                pytest.fail("submit click returned false")
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        # 6. Poll current_url for the project home.
        expected_token = encode_dir_token(str(expected_worktree.resolve()))
        if not _wait_for_project_url(mcp, expected_token, timeout_s=8.0):
            pytest.fail(
                f"did not navigate to /{expected_token} within deadline; "
                f"current_url={mcp.current_url()!r}"
            )

        # 7. Assert the created project is in the workspace / project list.
        # /project is the authoritative source of truth for the sidebar.
        target = expected_worktree.resolve()
        rows = http.list_projects()
        match = next(
            (p for p in rows if Path(p["worktree"]).resolve() == target),
            None,
        )
        assert match is not None, (
            f"no /project row for worktree {target}; "
            f"got ids {[r['id'] for r in rows]!r}"
        )
        created_project_id = match["id"]

        # Defensive: confirm it's not the currently-bound project (we never
        # want to delete /project/current).
        current_id = http.current_project()["id"]
        if created_project_id == current_id:
            pytest.skip(
                "scratch project collapsed onto /project/current — refusing "
                "to delete; will leave cleanup to tmp_path teardown"
            )

        # Also check the workspace list, which is the sidebar's view.
        # workspace_status is scoped to the current project so it may not
        # contain this new project; list_projects is the canonical check.
    finally:
        # 8. Clean up via HTTP (more reliable than UI confirm flow).
        if created_project_id is not None:
            try:
                http.delete_project(created_project_id)
            except Exception:
                pass
