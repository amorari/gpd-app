"""Phase 3 flow: gpd://session/<id> deep link resolves to the session route."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from gpd_tests.helpers.navigator import route_session

_LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework"
    "/Frameworks/LaunchServices.framework/Support/lsregister"
)


def _installed_release_paths() -> list[Path]:
    """Return existing GPD.app release install locations."""
    candidates = [
        Path("/Applications/GPD.app"),
        Path.home() / "Applications" / "GPD.app",
    ]
    return [p for p in candidates if p.exists()]


def _schemes_registered_for_gpd() -> set[str] | None:
    """Query lsregister for URL schemes claimed by any GPD bundle.

    Returns a set of bundle IDs that claim 'gpd' as a URL scheme, or None
    if lsregister is unavailable or the output cannot be parsed.
    """
    lsr_path = Path(_LSREGISTER)
    if not lsr_path.exists():
        return None
    try:
        result = subprocess.run(
            [str(lsr_path), "-dump"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    bundle_ids: set[str] = set()
    current_bundle: str | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        # lsregister -dump groups entries; bundle id lines look like:
        #   bundle id:    inc.psi.gpd
        if stripped.startswith("bundle id:"):
            current_bundle = stripped.split(":", 1)[1].strip()
        # URL scheme lines look like:
        #   url schemes:  gpd
        elif stripped.startswith("url schemes:") and current_bundle:
            schemes_text = stripped.split(":", 1)[1].strip()
            schemes = [s.strip() for s in schemes_text.split(",")]
            if "gpd" in schemes:
                bundle_ids.add(current_bundle)
    # Return the set (possibly empty) so callers can distinguish "lsregister
    # available but nothing registered" from "lsregister unavailable" (None).
    return bundle_ids


def _scheme_ambiguity() -> str | None:
    """Return a skip reason if `gpd://` is plausibly registered to multiple
    bundle ids, otherwise None.

    Primary check: query lsregister for actual URL scheme registration.
    Fallback heuristic: if a release GPD.app exists in /Applications or
    ~/Applications AND the running GPD is a dev build, both may claim the
    scheme and macOS dispatch is ambiguous.
    """
    # --- Primary: lsregister-based check ---
    registered_bundles = _schemes_registered_for_gpd()
    if registered_bundles is not None and len(registered_bundles) > 1:
        return (
            f"gpd:// scheme is registered by multiple bundle ids "
            f"({', '.join(sorted(registered_bundles))}); "
            "macOS dispatch is non-deterministic here. Run against a "
            "single registered bundle id."
        )
    if registered_bundles is not None and len(registered_bundles) == 0:
        return (
            "gpd:// URL scheme is not registered for this build; "
            "deep link dispatch requires a notarized or app-store install."
        )
    if registered_bundles is not None:
        # lsregister gave a definitive answer (exactly 1 claimant) — no need
        # for the fallback heuristic.
        return None

    # --- Fallback heuristic (lsregister unavailable) ---
    release_paths = _installed_release_paths()
    if not release_paths:
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
        locations = ", ".join(str(p) for p in release_paths)
        return (
            f"gpd:// scheme is claimed by both {locations} "
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
