"""Phase 3 flow: gpd://session/<id> deep link resolves to the session route."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from gpd_tests.helpers.navigator import route_session


def _scheme_ambiguity() -> str | None:
    """Return a skip reason if `gpd://` is plausibly registered to multiple
    bundle ids, otherwise None.

    Heuristic: if /Applications/GPD.app exists (release bundle id
    inc.psi.gpd) AND the currently-running GPD is launched from a
    different path (e.g. debug build under src-tauri/target), both apps
    claim the scheme and macOS dispatch is ambiguous.
    """
    release_installed = Path("/Applications/GPD.app").exists()
    if not release_installed:
        return None

    # Use `ps -eo command` to get full command-line paths of all processes.
    # On macOS, `pgrep -af` only prints PIDs (BSD pgrep ignores -l with -f),
    # so ps is more reliable for extracting the executable path.
    out = subprocess.run(
        ["ps", "-eo", "command"],
        capture_output=True,
        text=True,
        check=False,
    )
    running_paths = [
        line.strip()
        for line in out.stdout.splitlines()
        if ".app/Contents/MacOS/GPD" in line and "grep" not in line
    ]
    dev_build_running = any(
        "target/debug" in p or "target/release" in p or "GPD Dev.app" in p
        for p in running_paths
    )
    if dev_build_running:
        return (
            "gpd:// scheme is claimed by both /Applications/GPD.app "
            "(inc.psi.gpd) and the running dev build (inc.psi.gpd.dev); "
            "macOS dispatch is non-deterministic here. Run against a "
            "single registered bundle id."
        )
    return None


@pytest.fixture(autouse=True)
def _skip_on_scheme_ambiguity():
    """Skip this module's tests before any expensive fixture setup when
    gpd:// dispatch would be non-deterministic."""
    reason = _scheme_ambiguity()
    if reason:
        pytest.skip(reason)


@pytest.mark.flows
def test_deep_link_session_routes_to_session(http, mcp, scratch_project_dir):
    # Create a session so we have a real id to route to.
    session = http.create_session(directory=str(scratch_project_dir))
    sid = session["id"]

    # Trigger the deep link. `open` returns immediately; routing is async.
    try:
        subprocess.run(
            ["open", f"gpd://session/{sid}"],
            capture_output=True,
            check=True,
            timeout=5.0,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"`open gpd://session/{sid}` failed with code {e.returncode}: "
            f"{e.stderr.decode(errors='replace').strip()}. "
            "Is a gpd:// URL handler registered for any GPD bundle id?"
        )
    except subprocess.TimeoutExpired:
        pytest.fail("`open gpd://...` timed out after 5s")

    expected = route_session(sid)
    deadline = time.monotonic() + 10.0
    last = ""
    while time.monotonic() < deadline:
        try:
            last = mcp.current_url()
        except Exception:
            last = ""
        if last.endswith(f"/session/{sid}"):
            return
        time.sleep(0.2)
    pytest.fail(
        f"deep link did not route to /session/{sid}; current={last!r} "
        f"(expected prefix: {expected})"
    )
