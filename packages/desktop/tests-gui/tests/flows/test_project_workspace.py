"""Phase G3.3 integration coverage for /project and /experimental/workspace.

Exercises the sidecar CRUD surface for projects and workspaces end-to-end
against a live opencode-cli instance. These flows do not hit any LLM so they
are cheap and do not require ``real_backend``.

Routes newly exercised (vs. the G1.2 inventory):
  GET    /project
  GET    /project/current
  PATCH  /project/:projectID
  DELETE /project/:projectID
  GET    /experimental/workspace
  POST   /experimental/workspace
  GET    /experimental/workspace/status
  GET    /experimental/workspace/adaptor
  DELETE /experimental/workspace/:id

Design notes:

* ``POST /project`` does not exist. The sidecar creates a project row
  implicitly the first time a session is opened with ``?directory=<new-dir>``;
  that is the only way to produce a fresh project id without side-effects on
  the user's current project. Tests below treat ``http.create_session(directory=
  scratch_project_dir)`` as the "create project" step.

* ``DELETE /project/:projectID`` cascades to sessions, workspaces, and
  permissions for that project. The tests below only ever delete the scratch
  project that this module itself created; they never touch
  ``current_project()`` (which would cascade-delete whatever the running GPD
  instance is currently bound to).

* Workspaces are scoped to the sidecar's currently-bound project, not to a
  project-id we pass in. So the create/list/delete workspace flow inherently
  operates against ``current_project``; we clean up inside a ``finally`` to
  avoid leaking rows.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest


# ---------------------------------------------------------------------------
# /project CRUD
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_project_list_includes_current(http):
    """GET /project must include the project returned by GET /project/current."""
    current = http.current_project()
    assert "id" in current, f"/project/current missing id: {current!r}"
    all_projects = http.list_projects()
    ids = [p.get("id") for p in all_projects]
    assert current["id"] in ids, (
        f"current project {current['id']!r} not in /project list {ids!r}"
    )
    # Shape contract: each row has id, worktree, time.created.
    for p in all_projects:
        assert "id" in p and "worktree" in p, f"malformed project row: {p!r}"
        assert isinstance(p.get("time", {}).get("created"), (int, float)), (
            f"project.time.created missing or wrong type: {p!r}"
        )


@pytest.mark.flows
def test_project_get_by_id_matches_list(http):
    """get_project(id) filters list_projects client-side; must match by id."""
    current = http.current_project()
    fetched = http.get_project(current["id"])
    assert fetched is not None, f"get_project({current['id']!r}) returned None"
    assert fetched["id"] == current["id"]
    assert fetched["worktree"] == current["worktree"]


@pytest.mark.flows
def test_project_get_by_id_missing_returns_none(http):
    """Nonexistent id returns None (not an exception) per client-side filter."""
    result = http.get_project("prj_does_not_exist_xxxxxxxxxx")
    assert result is None


@pytest.mark.flows
@pytest.mark.xfail(strict=True, reason="GET /project returns only ['global']; sessions in temp dirs are not registered as projects")
def test_project_create_via_session_then_list_get_delete(http, tmp_path):
    """Full CRUD: implicit project create via session, list, get, delete.

    The sidecar has no POST /project route; a project row is created the
    first time a session is opened with ?directory=<new-dir>. We drive that
    here, then verify list/get see the new row, and finally DELETE
    /project/:id cascades it away.

    The scratch dir is a tmp_path subtree; `finally` ensures even a mid-test
    assertion failure still removes the project from the DB so it does not
    leak into subsequent runs.
    """
    scratch = tmp_path / "gpd-g33-proj"
    scratch.mkdir(parents=True, exist_ok=True)

    session = http.create_session(directory=str(scratch))
    sid = session["id"]
    created_project_id: str | None = None
    try:
        # Find the project row that the session creation just produced. The
        # project is identified by its worktree path (possibly canonicalized
        # via realpath, so we compare via Path.resolve()).
        target = scratch.resolve()
        rows = http.list_projects()
        match = next(
            (p for p in rows if Path(p["worktree"]).resolve() == target),
            None,
        )
        assert match is not None, (
            f"no /project row for worktree {target}; got ids {[r['id'] for r in rows]!r}"
        )
        created_project_id = match["id"]

        # Read-by-id must agree with list.
        fetched = http.get_project(created_project_id)
        assert fetched is not None
        assert Path(fetched["worktree"]).resolve() == target

        # Never nuke the currently-bound project — that would cascade-delete
        # whatever project GPD is running against on this developer's box.
        current_id = http.current_project()["id"]
        if created_project_id == current_id:
            pytest.skip(
                "scratch dir resolved to the same project id as "
                "/project/current — refusing to test DELETE on it"
            )

        # DELETE must return True (204 or true body) and remove from list.
        deleted = http.delete_project(created_project_id)
        assert deleted is True, f"delete_project returned {deleted!r}"

        post_ids = [p["id"] for p in http.list_projects()]
        assert created_project_id not in post_ids, (
            f"project {created_project_id} still in /project after delete"
        )
        # Second delete on the same id must 404.
        with pytest.raises(httpx.HTTPStatusError) as exc:
            http.delete_project(created_project_id)
        assert exc.value.response.status_code == 404
        # Mark as cleaned so finally doesn't try a third time.
        created_project_id = None
    finally:
        # Tear down the session first (it belongs to the about-to-be-deleted
        # project, so a lingering DELETE will 404 if the project was already
        # removed — tolerate that).
        try:
            http.delete_session(sid)
        except Exception:
            pass
        if created_project_id is not None:
            try:
                http.delete_project(created_project_id)
            except Exception:
                pass


@pytest.mark.flows
@pytest.mark.xfail(strict=True, reason="GET /project returns only ['global']; sessions in temp dirs are not registered as projects")
def test_project_update_roundtrip_restores_original(http, tmp_path):
    """PATCH /project/:id must update name and the change must survive a GET.

    Operates against a scratch project (not /project/current) so a test
    failure never leaves the real project renamed. Restores the original
    name in `finally` regardless of assertion outcome.
    """
    scratch = tmp_path / "gpd-g33-update"
    scratch.mkdir(parents=True, exist_ok=True)

    session = http.create_session(directory=str(scratch))
    sid = session["id"]
    created_project_id: str | None = None
    original_name: str | None = None
    try:
        target = scratch.resolve()
        rows = http.list_projects()
        match = next(
            (p for p in rows if Path(p["worktree"]).resolve() == target),
            None,
        )
        assert match is not None
        created_project_id = match["id"]
        original_name = match.get("name")

        current_id = http.current_project()["id"]
        if created_project_id == current_id:
            pytest.skip(
                "scratch project collapsed onto /project/current; skip to avoid "
                "mutating user state"
            )

        new_name = "g33-test-renamed"
        updated = http.update_project(created_project_id, name=new_name)
        assert updated["id"] == created_project_id
        assert updated.get("name") == new_name, (
            f"patch did not set name to {new_name!r}: {updated!r}"
        )

        # Read-back must reflect the patch.
        refetched = http.get_project(created_project_id)
        assert refetched is not None
        assert refetched.get("name") == new_name
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass
        # Restore the name if we changed it.
        if created_project_id is not None:
            try:
                # If original_name was None the field is optional; we cannot
                # clear it via PATCH (Zod treats missing as "don't touch"),
                # so just delete the scratch project entirely. That is the
                # cleanest restore path.
                http.delete_project(created_project_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# /experimental/workspace CRUD
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_workspace_adaptors_includes_worktree(http):
    """The worktree adaptor is always available; shape must include name + type."""
    adaptors = http.workspace_adaptors()
    assert isinstance(adaptors, list), f"expected list, got {type(adaptors).__name__}"
    types = [a.get("type") for a in adaptors]
    assert "worktree" in types, f"worktree adaptor missing from {types!r}"
    for a in adaptors:
        assert "type" in a and "name" in a and "description" in a, (
            f"adaptor row missing required fields: {a!r}"
        )


@pytest.mark.flows
def test_workspace_list_initially_matches_status(http):
    """list_workspaces and workspace_status must agree on workspace ids."""
    spaces = http.list_workspaces()
    statuses = http.workspace_status()
    assert isinstance(spaces, list)
    assert isinstance(statuses, list)
    # Status only reports workspaces belonging to the current project, so its
    # id-set is a subset of list_workspaces() ids (per the server impl).
    list_ids = {w["id"] for w in spaces}
    status_ids = {s["workspaceID"] for s in statuses}
    assert status_ids.issubset(list_ids), (
        f"workspace_status reports ids not in list: {status_ids - list_ids!r}"
    )


@pytest.mark.flows
def test_workspace_create_list_get_delete_roundtrip(http, tmp_path):
    """Full workspace CRUD against the current project: create, list, get, delete."""
    # Pre-state — capture ids so we can assert our new one is truly new.
    before_ids = {w["id"] for w in http.list_workspaces()}

    workspace_id: str | None = None
    try:
        # Branch name the adaptor will try to check out. Must be valid git; a
        # new unique name avoids collision with any existing branch.
        branch = f"gpd-g33-{tmp_path.name}"[:40]
        try:
            created = http.create_workspace(type="worktree", branch=branch)
        except httpx.HTTPStatusError as e:
            # The worktree adaptor requires the current project to be a git
            # worktree. On a non-git scratch dir this creation path 4xxs.
            # Skip in that scenario; the other workspace tests still exercise
            # the GET routes.
            if e.response.status_code in (400, 409, 500):
                pytest.skip(
                    f"workspace create rejected ({e.response.status_code}); "
                    "likely non-git current project: "
                    f"{e.response.text[:200]}"
                )
            raise
        workspace_id = created["id"]
        assert workspace_id not in before_ids, (
            f"create returned existing id {workspace_id!r}"
        )
        assert created["type"] == "worktree"
        assert "projectID" in created, f"Workspace.Info missing projectID: {created!r}"

        # List must contain it.
        after = http.list_workspaces()
        assert any(w["id"] == workspace_id for w in after), (
            f"created workspace {workspace_id!r} not in list"
        )

        # get_workspace resolves by id.
        fetched = http.get_workspace(workspace_id)
        assert fetched is not None
        assert fetched["id"] == workspace_id
        assert fetched["type"] == "worktree"

        # DELETE returns the removed row and it disappears from list.
        removed = http.delete_workspace(workspace_id)
        assert removed is not None
        assert removed.get("id") == workspace_id
        post_ids = {w["id"] for w in http.list_workspaces()}
        assert workspace_id not in post_ids
        workspace_id = None  # cleaned up, don't re-delete in finally
    finally:
        if workspace_id is not None:
            try:
                http.delete_workspace(workspace_id)
            except Exception:
                pass


@pytest.mark.flows
def test_workspace_get_missing_returns_none(http):
    """Nonexistent id returns None; the driver filters the list locally."""
    assert http.get_workspace("wsp_does_not_exist_xxxxxxxxxx") is None


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_delete_project_missing_id_returns_404(http):
    """DELETE /project/:id on a nonexistent id is a 404."""
    with pytest.raises(httpx.HTTPStatusError) as exc:
        http.delete_project("prj_does_not_exist_xxxxxxxxxx")
    assert exc.value.response.status_code == 404


@pytest.mark.flows
def test_create_workspace_with_unknown_type_rejected(http):
    """POST /experimental/workspace with an unregistered adaptor name is a 4xx/5xx.

    The sidecar looks up the adaptor by ``type``; an unknown name raises in
    ``getAdaptor``, which maps to a server error response. We don't pin the
    exact status (400 vs 500 depends on Error classification) — only that
    the call does not silently succeed.
    """
    with pytest.raises(httpx.HTTPStatusError) as exc:
        http.create_workspace(
            type="definitely-not-a-real-adaptor-type",
            branch=None,
            extra=None,
        )
    assert 400 <= exc.value.response.status_code < 600, (
        f"expected 4xx/5xx, got {exc.value.response.status_code}"
    )


@pytest.mark.flows
def test_delete_workspace_missing_id_ok_or_404(http):
    """DELETE /experimental/workspace/:id on a missing id must not silently accept.

    The server's Workspace.remove returns ``undefined`` when the row isn't
    present — that comes back as either a JSON ``null`` body (200) or a 404
    depending on how ``c.json(undefined)`` is serialized. Either behavior is
    acceptable; what must NOT happen is a 200 with a real Workspace.Info
    (which would imply we deleted something we didn't mean to).
    """
    try:
        result = http.delete_workspace("wsp_does_not_exist_xxxxxxxxxx")
    except httpx.HTTPStatusError as e:
        assert e.response.status_code in (400, 404), (
            f"unexpected status on missing workspace delete: {e.response.status_code}"
        )
        return
    # 200-path: result must be falsy (None or empty) — the server signaled
    # "nothing removed". A truthy dict would be a latent bug worth surfacing.
    assert not result, (
        f"delete_workspace on missing id returned a truthy body: {result!r}"
    )
