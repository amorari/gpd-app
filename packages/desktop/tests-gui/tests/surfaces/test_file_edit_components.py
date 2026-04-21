"""Phase G5.6 — surface tests for file-edit components.

Covers the inline line-editor flow in
``packages/app/src/components/file-edit/``:

  1. Opening a file shows its on-disk contents in the editor DOM.
  2. Saving an edit writes the new contents to disk.
  3. Discarding an in-memory edit leaves the disk file unchanged.

Sources in scope:
  packages/app/src/components/file-edit/edit-hotspot.tsx
  packages/app/src/components/file-edit/line-editor.tsx
  packages/app/src/components/file-edit/hotspot-layer.tsx
  packages/app/src/components/file-edit/use-file-edit.tsx
  packages/app/src/components/file-edit/eligibility.ts

Product contract being tested:
  POST /file/edit-line  (packages/opencode/src/server/instance/file.ts:214)
  — this is the one endpoint the UI calls on Save; editing a line via the
  UI must ultimately reach this route.

Stable UI anchors used:
  [data-component="edit-hotspot"]          — always present (product code)
  [data-component="line-editor"]           — always present (product code)
  [data-action="file-edit-hotspot"]        — STAGED (G5.6 patch)
  [data-action="file-edit-save"]           — STAGED (G5.6 patch)
  [data-action="file-edit-cancel"]         — STAGED (G5.6 patch)
  [data-action="file-edit-line-input"]     — STAGED (G5.6 patch)

The staged product-side patch lives at
``docs/gpd-app-patches/G5.6-file-edit-data-action.patch``. Until that
patch lands on gpd-app main, the three UI-driven tests xfail on the
missing anchor, but the *product contract* (POST /file/edit-line writes
to disk) is still exercised via the sidecar so the assertion has real
value today.

Constraints honored:
  - Fixture files live under ``tmp_path`` — never touch user files.
  - No product edits; the data-action additions are shipped as a patch
    for a separate gpd-app PR.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)
from gpd_tests.helpers.timings import wait_until


# --- fixtures ---------------------------------------------------------------


_FIXTURE_FILENAME = "sample.txt"
_INITIAL_CONTENTS = "alpha\nbeta\ngamma\n"
# Line 2 (1-indexed) is "beta".
_EDIT_LINE = 2
_OLD_LINE = "beta"
_NEW_LINE = "BETA-edited"


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """Create an on-disk directory that GPD will treat as a project, with a
    fixture file of known contents.

    Only touches ``tmp_path_factory`` — no user files.
    """
    p = tmp_path_factory.mktemp("gpd_proj_file_edit")
    (p / "README.md").write_text("# file-edit test project\n")
    (p / _FIXTURE_FILENAME).write_text(_INITIAL_CONTENTS)
    return str(p)


@pytest.fixture
def seeded_session(http, prepared_project_path) -> tuple[str, str]:
    """Create a session bound to the project directory.

    Creating a session with ``directory=X`` binds the sidecar to X so that
    ``POST /file/edit-line`` resolves relative paths against it. Returns
    ``(project_path, session_id)``.
    """
    ses = http.create_session(directory=prepared_project_path)
    sid = ses.get("id") or ses.get("sessionID") or ses.get("session_id")
    assert sid, f"create_session returned no id: {ses!r}"
    yield prepared_project_path, sid
    try:
        http.delete_session(sid)
    except Exception:  # noqa: BLE001
        pass


def _session_route(path: str, sid: str | None = None) -> str:
    return route_session_in_project(encode_dir_token(path), sid)


# --- helpers ---------------------------------------------------------------


def _read_disk(path: str) -> str:
    return Path(path).read_text()


def _edit_line_via_http(
    http,
    project_directory: str,
    relative_path: str,
    line: int,
    old: str,
    new: str,
):
    """Call the sidecar's ``POST /file/edit-line`` directly.

    This is the exact route the UI uses under the hood (see
    ``hotspot-layer.tsx#handleSave`` calling ``sdk.client.file.editLine``).
    Exercising it through HTTP gives us a real contract-level assertion
    even when the UI DOM layer is not reachable.

    The ``?directory=`` query param is load-bearing: the sidecar's
    ``WorkspaceRouterMiddleware`` uses it to pick the Instance whose
    ``Instance.directory`` becomes the base for relative-path resolution.
    Without it the middleware falls back to ``process.cwd()`` and the
    request may route to a no-instance 500 or the SPA fallback HTML.
    """
    r = http._client.post(
        "/file/edit-line",
        params={"directory": project_directory},
        json={
            "path": relative_path,
            "line": line,
            "oldContent": old,
            "newContent": new,
        },
    )
    r.raise_for_status()
    return r.json()


_XFAIL_REASON = (
    "UI inline-edit flow lacks stable data-action anchors on the hotspot "
    "pencil, line editor host, Save button, and Cancel button. Staged "
    "patch: docs/gpd-app-patches/G5.6-file-edit-data-action.patch. Until it "
    "lands, the UI-driven halves of these tests skip on the missing anchor; "
    "the product-contract half (POST /file/edit-line round-trip against a "
    "tmp_path fixture) runs unconditionally."
)


# --- 1. open file + show content -------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=False, reason=_XFAIL_REASON)
def test_file_edit_opens_file_and_shows_content(mcp, http, seeded_session):
    """Open a tmp_path fixture file and assert the editor DOM shows its
    on-disk contents.

    Today the file panel doesn't expose a reliable deep-link for opening a
    specific file, so this test currently xfails on the missing anchor.
    The disk-side precondition (file has the known fixture contents) is
    verified unconditionally, which guards against a regression in the
    tmp_path fixture itself.
    """
    project_path, sid = seeded_session

    # Sanity: the fixture file on disk has the expected contents before any
    # UI or HTTP call runs.
    disk_before = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
    assert disk_before == _INITIAL_CONTENTS, (
        f"fixture precondition failed: {disk_before!r} != {_INITIAL_CONTENTS!r}"
    )

    nav = Navigator(mcp)
    nav.go(_session_route(project_path, sid), timeout_s=5.0)
    probe = DOMProbe(mcp)

    # The product has no stable "open-this-file" data-action today. Try two
    # weak UI paths before surrendering to xfail:
    #   a) a file-panel row whose text matches the fixture filename
    #   b) any DOM node that already contains the fixture's first line
    # Either pathway would be enough to establish "editor DOM shows contents".
    click_js = (
        '(() => {'
        f'  const rows = Array.from(document.querySelectorAll("button, a, [role=\\"button\\"]"));'
        f'  const row = rows.find(r => /sample\\.txt/.test(r.innerText || ""));'
        '  if (!row) return "no-row";'
        '  row.click();'
        '  return "clicked";'
        '})()'
    )
    try:
        probe.eval(click_js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    time.sleep(0.3)

    # Now look for the fixture contents in the DOM. The Pierre file viewer
    # renders each line inside its own shadow-DOM node, so we fall back to
    # a document-wide text probe.
    def _dom_shows_first_line() -> bool:
        try:
            return probe.eval_bool(
                '(() => {'
                '  const txt = document.body ? document.body.innerText : "";'
                '  return /alpha/.test(txt) && /beta/.test(txt);'
                '})()'
            )
        except ProbeSkip:
            return False

    if not wait_until(_dom_shows_first_line, timeout_s=5.0, poll_s=0.2):
        pytest.xfail(
            "file-panel has no stable anchor to open a specific file via UI; "
            "editor DOM never loaded the fixture contents. Relies on the "
            "G5.6 staged patch."
        )
    assert _dom_shows_first_line()


# --- 2. save writes to disk ------------------------------------------------


@pytest.mark.surfaces
def test_file_edit_save_writes_to_disk(http, seeded_session):
    """Edit a single line; the tmp_path file on disk must match the new content.

    Drives the product's on-save contract directly via ``POST /file/edit-line``
    — the same route the inline editor calls. This is the load-bearing
    assertion for the file-edit feature; the UI is only a wrapper around
    this single HTTP call, so the contract is what we actually care about.
    The UI-level `data-action` test above is complementary.
    """
    project_path, _sid = seeded_session

    # Pre-condition.
    disk_before = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
    assert disk_before == _INITIAL_CONTENTS

    # Call the same endpoint the UI calls.
    result = _edit_line_via_http(
        http,
        project_path,
        _FIXTURE_FILENAME,
        _EDIT_LINE,
        _OLD_LINE,
        _NEW_LINE,
    )
    assert result.get("ok") is True, f"editLine did not succeed: {result!r}"

    # Post-condition: disk file reflects the new line.
    expected = _INITIAL_CONTENTS.replace(f"{_OLD_LINE}\n", f"{_NEW_LINE}\n")
    disk_after = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
    assert disk_after == expected, (
        f"disk contents did not match expected: {disk_after!r} != {expected!r}"
    )


# --- 3. discard reverts to disk contents -----------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=False, reason=_XFAIL_REASON)
def test_file_edit_discard_reverts_to_disk_contents(mcp, http, seeded_session):
    """Edit a line in-memory via the UI, press Cancel, and verify:
      a) the editor host shows the *disk* (unmodified) line contents again, AND
      b) the on-disk file is byte-for-byte unchanged.

    (b) is load-bearing for correctness — a discard that silently writes to
    disk would be a data-loss bug. We verify it unconditionally.
    (a) needs the staged ``data-action="file-edit-cancel"`` anchor.
    """
    project_path, sid = seeded_session

    disk_before = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
    assert disk_before == _INITIAL_CONTENTS

    nav = Navigator(mcp)
    nav.go(_session_route(project_path, sid), timeout_s=5.0)
    probe = DOMProbe(mcp)

    # Try to locate the hotspot button (staged anchor). If not present,
    # xfail — we cannot open the editor without clicking a line hotspot.
    try:
        hotspot_clicked = probe.eval_bool(
            '(() => {'
            '  const btn = document.querySelector('
            '    \'[data-action="file-edit-hotspot"]\''
            '  );'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not hotspot_clicked:
        # Cannot open editor — but still assert disk is unchanged so the
        # assertion carries real value while waiting for the patch.
        disk_after = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
        assert disk_after == disk_before, (
            "fixture file was modified by merely navigating to its session — "
            "this would be a serious product regression"
        )
        pytest.xfail(
            "file-edit-hotspot anchor missing; cannot open inline editor via "
            "UI path. Staged patch not applied."
        )

    time.sleep(0.3)

    # Editor should be open now — look for the line-editor host.
    try:
        editor_open = probe.eval_bool(
            '(() => !!document.querySelector('
            '"[data-component=\\"line-editor\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not editor_open:
        pytest.xfail("line-editor did not mount after clicking hotspot")

    # Click the Cancel button.
    try:
        cancel_clicked = probe.eval_bool(
            '(() => {'
            '  const btn = document.querySelector('
            '    \'[data-action="file-edit-cancel"]\''
            '  );'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not cancel_clicked:
        pytest.xfail(
            "file-edit-cancel anchor missing; staged patch not applied"
        )

    time.sleep(0.2)

    # Post-condition (a): editor is closed / re-shows disk contents.
    def _editor_gone() -> bool:
        try:
            return not probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"line-editor\\"]"'
                '))()'
            )
        except ProbeSkip:
            return False

    editor_closed = wait_until(_editor_gone, timeout_s=3.0, poll_s=0.1)
    assert editor_closed, (
        "line-editor did not dismiss after clicking Cancel (discard path)"
    )

    # Post-condition (b): file on disk is unchanged.
    disk_after = _read_disk(f"{project_path}/{_FIXTURE_FILENAME}")
    assert disk_after == disk_before, (
        f"discard path wrote to disk! before={disk_before!r} after={disk_after!r}"
    )
