"""GPD application-lifecycle helpers."""
from __future__ import annotations

import os
import re
import signal
import subprocess
from pathlib import Path

from gpd_tests.drivers.mcp import _discover_socket_path
from gpd_tests.helpers.timings import wait_until

def _default_app_path() -> str:
    """Resolve the GPD app bundle path.

    Order:
      1. GPD_APP_PATH env override
      2. Installed /Applications/GPD.app (production)
      3. In-tree debug build  (packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app)
      4. In-tree release build (…/release/…/GPD.app)
    """
    if env := os.environ.get("GPD_APP_PATH"):
        return env

    prod = "/Applications/GPD.app"
    if os.path.exists(prod):
        return prod

    # Walk up from this file to the repo root and probe the Tauri bundle dirs.
    here = Path(__file__).resolve()
    # gpd_tests/pages/app_state.py → tests-gui → desktop → packages → repo root
    desktop = here.parents[3]
    bundle_base = desktop / "src-tauri" / "target"
    for variant, name in [("debug", "GPD Dev.app"), ("release", "GPD.app")]:
        candidate = bundle_base / variant / "bundle" / "macos" / name
        if candidate.exists():
            return str(candidate)

    return prod  # fall back; will fail loudly if missing


APP_PATH = _default_app_path()

# Derive app name (bundle label) from the .app path: "GPD Dev" or "GPD".
# NOTE: the binary inside Tauri's bundle uses `mainBinaryName`, not the product
# name — debug builds ship `GPD Dev.app/Contents/MacOS/GPD` (no " Dev"). Match
# on the MacOS/ directory prefix so we don't have to replicate Tauri's naming.
_APP_NAME = Path(APP_PATH).stem
# Include the binary name so we match only the GPD main process and not the
# opencode-cli sidecar (which also lives under Contents/MacOS/).
_PGREP_PATTERN = f"{_APP_NAME}.app/Contents/MacOS/GPD"


def _pgrep(pattern: str) -> list[int]:
    # macOS pgrep -f silently fails when the pattern contains spaces
    # (e.g. "GPD Dev.app/Contents/MacOS/"). Use ps and filter in Python.
    out = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, command = parts
        if pid_str.isdigit() and re.search(pattern, command):
            pids.append(int(pid_str))
    return pids


class AppState:
    def __init__(self) -> None:
        self._launched_pid: int | None = None

    def is_running(self) -> bool:
        return bool(_pgrep(_PGREP_PATTERN))

    def gpd_pid(self) -> int | None:
        pids = _pgrep(_PGREP_PATTERN)
        return pids[0] if pids else None

    def sidecar_pid(self) -> int | None:
        """Return the opencode-cli serve pid.

        Preference order:
        1. A sidecar whose PPID matches ``_launched_pid`` (the Popen PID).
        2. A sidecar whose PPID matches *any* currently-running GPD process.
           Needed after quit+relaunch when macOS ``open -a`` spawns a second
           GPD process (PID B) and the sidecar is parented to B while
           ``_launched_pid`` still holds the original Popen PID (A).
        3. ``pids[0]`` — after ``wait_launched()`` confirmed the sidecar is
           healthy, there is exactly one sidecar and it is ours.  Falling back
           here avoids returning None when PPID tracking breaks entirely.
        """
        pids = _pgrep("opencode-cli.*serve")
        if not pids:
            return None

        # Collect the set of all live GPD process PIDs for step-2 matching.
        gpd_pids = set(_pgrep(_PGREP_PATTERN))

        # Step 1 + 2: check PPID of each sidecar candidate.
        step1_match: int | None = None
        step2_match: int | None = None
        for pid in pids:
            try:
                out = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                ppid_raw = out.stdout.strip()
                if not ppid_raw.isdigit():
                    continue
                ppid = int(ppid_raw)
                if self._launched_pid is not None and ppid == self._launched_pid:
                    step1_match = pid
                    break  # Best possible match — stop searching.
                if ppid in gpd_pids and step2_match is None:
                    step2_match = pid
            except Exception:
                continue

        if step1_match is not None:
            return step1_match
        if step2_match is not None:
            return step2_match
        # Step 3: PPID matching failed entirely — return the only known sidecar.
        return pids[0]

    def kill_stale(self) -> None:
        """Terminate any leftover GPD / opencode-cli processes."""
        for pattern in (_PGREP_PATTERN, "opencode-cli.*serve"):
            for pid in _pgrep(pattern):
                subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    capture_output=True,
                    check=False,
                )
        # Poll after SIGTERM; if still alive, escalate to SIGKILL.
        alive = lambda: bool(
            _pgrep(_PGREP_PATTERN) or _pgrep("opencode-cli.*serve")
        )
        if not wait_until(lambda: not alive(), timeout_s=3.0):
            # SIGTERM wasn't enough — send SIGKILL to remaining processes.
            survivors = []
            for pattern in (_PGREP_PATTERN, "opencode-cli.*serve"):
                survivors.extend(_pgrep(pattern))
            print(
                f"kill_stale: escalating to SIGKILL for pids {survivors}"
            )
            for pid in survivors:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if not wait_until(lambda: not alive(), timeout_s=5.0):
                raise TimeoutError(
                    "kill_stale: processes still alive after SIGKILL"
                )

    def launch(self) -> None:
        """Launch GPD as a detached process and record the exact PID.

        Using open -a can produce a late second process when it silently
        succeeds exit-code-wise but lags behind a Popen fallback, creating
        two GPD instances whose PPIDs confuse sidecar_pid(). Launching via
        Popen directly avoids the race and gives us proc.pid immediately.
        """
        binary = Path(APP_PATH) / "Contents" / "MacOS" / "GPD"
        if not binary.exists():
            binary_dir = Path(APP_PATH) / "Contents" / "MacOS"
            candidates = [
                f for f in binary_dir.iterdir()
                if f.is_file() and f.name != "opencode-cli"
            ]
            if not candidates:
                raise RuntimeError(f"No binary found in {binary_dir}")
            binary = candidates[0]
        proc = subprocess.Popen(
            [str(binary)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._launched_pid = proc.pid
        timeout_s = 10.0
        ok = wait_until(lambda: self.is_running(), timeout_s=timeout_s)
        if not ok:
            pids = _pgrep(_PGREP_PATTERN)
            pids_str = ",".join(str(p) for p in pids) if pids else "none"
            raise RuntimeError(
                f"GPD failed to launch within {timeout_s}s "
                f"(matching pids: {pids_str})"
            )
        # Bring the app to the foreground so the webview is active.
        # open -a on an already-running app activates the existing window
        # without spawning a second process — safe to call here.
        subprocess.run(
            ["open", "-a", APP_PATH],
            capture_output=True,
            check=False,
        )

    def quit(self) -> None:
        subprocess.run(
            ["osascript", "-e", f'tell application "{_APP_NAME}" to quit'],
            capture_output=True,
            check=False,
        )
        self.wait_quit()
        self._launched_pid = None

    def refresh_launched_pid(self) -> None:
        """Re-bind parent/PPID tracking to the currently-running GPD.

        Call after any out-of-band restart (restart_app, tier reset, manual
        relaunch) so sidecar_pid() keeps matching against the live process
        instead of a stale PID.
        """
        self._launched_pid = self.gpd_pid()

    def wait_launched(self, *, timeout_s: float = 20.0) -> None:
        from gpd_tests.drivers.mcp import MCPClient, MCPError, MCPTimeout

        def _mcp_ready() -> bool:
            if not self.is_running():
                return False
            try:
                sock = _discover_socket_path()
            except FileNotFoundError:
                return False
            if not os.path.exists(sock):
                return False
            # Socket file alone isn't proof: after restart it can persist
            # while the new GPD instance is still starting. Probe via ping.
            # An auth-related rejection proves the peer is alive and speaking
            # MCP — treat it as ready. The mcp fixture handles token setup.
            try:
                MCPClient(socket_path=sock, timeout_s=2.0).ping()
                return True
            except Exception as e:
                msg = str(e).lower()
                if "auth" in msg or "token" in msg or "unauthoriz" in msg:
                    return True
                return False

        ok = wait_until(_mcp_ready, timeout_s=timeout_s)
        if not ok:
            raise TimeoutError(
                "GPD did not reach a running+socket state in time"
            )
        # Rebind parent-PID tracking so sidecar_pid() matches the live tree
        # after restart/reset/manual relaunch.
        self.refresh_launched_pid()

        # Wait for the opencode-cli sidecar to start.  The MCP socket being
        # available only means the Tauri host is ready; the sidecar spawns
        # asynchronously and may lag by several seconds on first launch.
        # Tests that call http.rediscover() after a relaunch need sidecar_pid()
        # to return a live PID, so we gate here rather than forcing every test
        # to implement its own wait.
        sidecar_ok = wait_until(
            lambda: self.sidecar_pid() is not None,
            timeout_s=15.0,
        )
        if not sidecar_ok:
            raise TimeoutError(
                "opencode-cli sidecar did not start within 15s of GPD launch"
            )

        # Wait for the webview JS bridge to be STABLY responsive.
        # MCP ping only proves the socket listener is up; execute_js routes
        # through the webview which mounts asynchronously.  On a cold start,
        # the webview has a brief transient window (during SolidJS hydration)
        # where execute_js succeeds for 1-2 calls then times out again.
        # Requiring 3 consecutive successes filters out that transient state
        # and ensures tests never trigger execute_js before it is truly ready.
        #
        # Recovery: if the bridge is dead because the webview was left at
        # tauri://localhost/ from a previous run (cross-protocol navigation
        # breaks Tauri IPC bridge injection in cfg(dev) mode), a one-time
        # redirect to the devUrl (http://localhost:1420) restores the bridge
        # immediately without a full GPD restart.
        _consecutive_ok = [0]
        _bridge_recovery_attempted = [False]
        _bridge_fail_count = [0]
        _RECOVERY_AFTER_FAILURES = 10  # ~20s at poll_s=2.0

        def _js_bridge_ready() -> bool:
            try:
                MCPClient(timeout_s=3.0).execute_js("null")
                _consecutive_ok[0] += 1
                return _consecutive_ok[0] >= 3
            except (FileNotFoundError, ConnectionRefusedError):
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1
            except MCPTimeout:
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1
            except MCPError as e:
                msg = str(e).lower()
                if "timeout" in msg:
                    _consecutive_ok[0] = 0
                    _bridge_fail_count[0] += 1
                else:
                    # Non-timeout MCPError (e.g. auth): bridge replied — count it.
                    _consecutive_ok[0] += 1
                    return _consecutive_ok[0] >= 3
            except Exception:
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1

            # After repeated failures, try once to redirect to the devUrl.
            # This recovers from a stale tauri://localhost/ state left by a
            # prior test run (navigating back to http://localhost:1420 re-injects
            # the Tauri IPC bridge initialization scripts which are per-origin).
            if (
                not _bridge_recovery_attempted[0]
                and _bridge_fail_count[0] >= _RECOVERY_AFTER_FAILURES
            ):
                _bridge_recovery_attempted[0] = True
                try:
                    # Only redirect if the webview is currently at tauri://.
                    current = MCPClient(timeout_s=2.0).current_url()
                    if current.startswith("tauri://"):
                        MCPClient(timeout_s=5.0).navigate("http://localhost:1420")
                except Exception:
                    pass
                _consecutive_ok[0] = 0  # reset counter after recovery attempt

            return False

        js_ok = wait_until(_js_bridge_ready, timeout_s=60.0, poll_s=2.0)
        if not js_ok:
            raise TimeoutError(
                "GPD webview JS bridge (execute_js) did not reach stable "
                "responsiveness within 60s of launch"
            )

    def wait_quit(self, *, timeout_s: float = 10.0) -> None:
        ok = wait_until(lambda: not self.is_running(), timeout_s=timeout_s)
        if not ok:
            raise TimeoutError("GPD did not quit in time")
