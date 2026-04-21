"""Shape-only tests for HTTPClient /project and /workspace helpers.

Unit-level TDD for Task G3.3. No live GPD required; uses httpx.MockTransport
to pin request shape and response parsing.

Routes covered (see docs/coverage-expansion/inventory/sidecar-routes.md):
  GET    /project
  GET    /project/current
  POST   /project/git/init
  PATCH  /project/:projectID
  DELETE /project/:projectID
  GET    /experimental/workspace
  POST   /experimental/workspace
  GET    /experimental/workspace/status
  GET    /experimental/workspace/adaptor
  DELETE /experimental/workspace/:id
"""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _client(**kwargs) -> HTTPClient:
    return HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        **kwargs,
    )


def _mock(routes: dict[tuple[str, str], tuple[int, object]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in routes:
            return httpx.Response(404, json={"error": f"no route {key}"})
        status, body = routes[key]
        if body is None:
            return httpx.Response(status, content=b"")
        if isinstance(body, (dict, list, bool)):
            return httpx.Response(status, json=body)
        return httpx.Response(status, content=body)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# /project routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_projects_returns_list():
    transport = _mock({
        ("GET", "/project"): (
            200,
            [
                {
                    "id": "prj_abc",
                    "worktree": "/tmp/a",
                    "time": {"created": 1, "updated": 1},
                    "sandboxes": [],
                }
            ],
        ),
    })
    with _client(transport=transport) as c:
        result = c.list_projects()
    assert isinstance(result, list)
    assert result[0]["id"] == "prj_abc"
    assert result[0]["worktree"] == "/tmp/a"


@pytest.mark.unit
def test_current_project_returns_info():
    transport = _mock({
        ("GET", "/project/current"): (
            200,
            {
                "id": "prj_cur",
                "worktree": "/tmp/cur",
                "time": {"created": 1, "updated": 2},
                "sandboxes": [],
            },
        ),
    })
    with _client(transport=transport) as c:
        result = c.current_project()
    assert result["id"] == "prj_cur"
    assert result["worktree"] == "/tmp/cur"


@pytest.mark.unit
def test_update_project_sends_patch_without_projectid_in_body():
    """PATCH /project/:id body is UpdateInput minus projectID."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "prj_abc",
                "worktree": "/tmp/a",
                "name": "new-name",
                "time": {"created": 1, "updated": 3},
                "sandboxes": [],
            },
        )

    with _client(transport=httpx.MockTransport(handler)) as c:
        out = c.update_project("prj_abc", name="new-name")
    req = seen[0]
    assert req.method == "PATCH"
    assert req.url.path == "/project/prj_abc"
    body = json.loads(req.content) if req.content else {}
    assert body == {"name": "new-name"}
    assert "projectID" not in body, (
        "projectID must NOT appear in body (zod strips it silently)"
    )
    assert out["name"] == "new-name"


@pytest.mark.unit
def test_delete_project_accepts_204():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204, content=b"")

    with _client(transport=httpx.MockTransport(handler)) as c:
        out = c.delete_project("prj_abc")
    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/project/prj_abc"
    # 204 → None body → delete_project returns True to mirror delete_session.
    assert out is True


@pytest.mark.unit
def test_delete_project_404_raises():
    transport = _mock({
        ("DELETE", "/project/prj_missing"): (404, {"error": "not found"}),
    })
    with _client(transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            c.delete_project("prj_missing")
    assert exc.value.response.status_code == 404


@pytest.mark.unit
def test_project_git_init_posts_and_returns_info():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "prj_abc",
                "worktree": "/tmp/a",
                "vcs": "git",
                "time": {"created": 1, "updated": 5},
                "sandboxes": [],
            },
        )

    with _client(transport=httpx.MockTransport(handler)) as c:
        out = c.project_git_init()
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/project/git/init"
    assert out["vcs"] == "git"


# ---------------------------------------------------------------------------
# /experimental/workspace routes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_workspaces_returns_list():
    transport = _mock({
        ("GET", "/experimental/workspace"): (
            200,
            [
                {
                    "id": "wsp_a",
                    "type": "worktree",
                    "name": "alpha",
                    "branch": None,
                    "directory": "/tmp/a",
                    "extra": None,
                    "projectID": "prj_abc",
                }
            ],
        ),
    })
    with _client(transport=transport) as c:
        result = c.list_workspaces()
    assert isinstance(result, list)
    assert result[0]["id"] == "wsp_a"
    assert result[0]["projectID"] == "prj_abc"


@pytest.mark.unit
def test_create_workspace_sends_body_without_projectid():
    """POST /experimental/workspace body is CreateInput minus projectID; the
    sidecar attaches the current project id server-side."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "wsp_new",
                "type": "worktree",
                "name": "alpha",
                "branch": None,
                "directory": "/tmp/a",
                "extra": None,
                "projectID": "prj_abc",
            },
        )

    with _client(transport=httpx.MockTransport(handler)) as c:
        out = c.create_workspace(type="worktree", branch=None, extra=None)
    req = seen[0]
    assert req.method == "POST"
    assert req.url.path == "/experimental/workspace"
    body = json.loads(req.content) if req.content else {}
    assert body["type"] == "worktree"
    assert body.get("branch") is None
    assert "projectID" not in body, (
        "projectID must NOT appear in body — server attaches from Instance.project.id"
    )
    assert out["id"] == "wsp_new"


@pytest.mark.unit
def test_get_workspace_returns_match_from_list():
    transport = _mock({
        ("GET", "/experimental/workspace"): (
            200,
            [
                {
                    "id": "wsp_a",
                    "type": "worktree",
                    "name": "alpha",
                    "branch": None,
                    "directory": "/tmp/a",
                    "extra": None,
                    "projectID": "prj_abc",
                },
                {
                    "id": "wsp_b",
                    "type": "worktree",
                    "name": "beta",
                    "branch": None,
                    "directory": "/tmp/b",
                    "extra": None,
                    "projectID": "prj_abc",
                },
            ],
        ),
    })
    with _client(transport=transport) as c:
        result = c.get_workspace("wsp_b")
    assert result is not None
    assert result["id"] == "wsp_b"
    assert result["name"] == "beta"


@pytest.mark.unit
def test_get_workspace_missing_returns_none():
    transport = _mock({
        ("GET", "/experimental/workspace"): (200, []),
    })
    with _client(transport=transport) as c:
        result = c.get_workspace("wsp_missing")
    assert result is None


@pytest.mark.unit
def test_delete_workspace_sends_delete():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "wsp_a",
                "type": "worktree",
                "name": "alpha",
                "branch": None,
                "directory": "/tmp/a",
                "extra": None,
                "projectID": "prj_abc",
            },
        )

    with _client(transport=httpx.MockTransport(handler)) as c:
        out = c.delete_workspace("wsp_a")
    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/experimental/workspace/wsp_a"
    assert out is not None
    assert out["id"] == "wsp_a"


@pytest.mark.unit
def test_workspace_status_returns_list():
    transport = _mock({
        ("GET", "/experimental/workspace/status"): (
            200,
            [{"workspaceID": "wsp_a", "status": "connected"}],
        ),
    })
    with _client(transport=transport) as c:
        result = c.workspace_status()
    assert isinstance(result, list)
    assert result[0]["workspaceID"] == "wsp_a"
    assert result[0]["status"] == "connected"


@pytest.mark.unit
def test_workspace_adaptors_returns_list():
    transport = _mock({
        ("GET", "/experimental/workspace/adaptor"): (
            200,
            [{"type": "worktree", "name": "Worktree", "description": "Local worktree"}],
        ),
    })
    with _client(transport=transport) as c:
        result = c.workspace_adaptors()
    assert isinstance(result, list)
    assert result[0]["type"] == "worktree"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_projects_401_raises():
    transport = _mock({
        ("GET", "/project"): (401, {"error": "auth"}),
    })
    with _client(transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            c.list_projects()
    assert exc.value.response.status_code == 401


@pytest.mark.unit
def test_create_workspace_400_raises():
    transport = _mock({
        ("POST", "/experimental/workspace"): (400, {"error": "bad input"}),
    })
    with _client(transport=transport) as c:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            c.create_workspace(type="worktree")
    assert exc.value.response.status_code == 400
