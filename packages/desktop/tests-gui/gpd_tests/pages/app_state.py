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

    Order: GPD_APP_PATH env override > installed /Applications/GPD.app.
    In-tree builds land at
    packages/desktop/src-tauri/target/{debug,release}/bundle/macos/:
      - debug build: GPD Dev.app
      - release build: GPD.app
    Point GPD_APP_PATH there when running against a local build.
    """
    return os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")


APP_PATH = _default_app_path()

# Derive app name (bundle label) from the .app path: "GPD Dev" or "GPD".
# NOTE: the binary inside Tauri's bundle uses `mainBinaryName`, not the product
# name — debug builds ship `GPD Dev.app/Contents/MacOS/GPD` (no " Dev"). Match
# on the MacOS/ directory prefix so we don't have to replicate Tauri's naming.
_APP_NAME = Path(APP_PATH).stem
_PGREP_PATTERN = f"{_APP_NAME}.app/Contents/MacOS/"


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

        When this AppState launched GPD, prefer the sidecar whose parent is
        our launched GPD process — avoids attaching to a stale unrelated
        opencode-cli instance. Returns None when PPID lookup fails for all
        pids (returning an unrelated sidecar is worse than failing loudly).
        """
        pids = _pgrep("opencode-cli.*serve")
        if not pids:
            return None
        parent = self._launched_pid
        if parent is None:
            return pids[0]
        for pid in pids:
            try:
                out = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                ppid_raw = out.stdout.strip()
                if ppid_raw.isdigit() and int(ppid_raw) == parent:
                    return pid
            except Exception:
                continue
        # PPID lookup failed for all pids — return None rather than an
        # unrelated sidecar, so the caller can fail loudly.
        return None

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
        """Launch GPD frontmost so the webview is active and MCP responds."""
        args = ["open", "-a", APP_PATH]
        subprocess.run(args, check=True, timeout=30)
        timeout_s = 10.0
        ok = wait_until(lambda: self.is_running(), timeout_s=timeout_s)
        if not ok:
            pids = _pgrep(_PGREP_PATTERN)
            pids_str = ",".join(str(p) for p in pids) if pids else "none"
            raise RuntimeError(
                f"GPD failed to launch within {timeout_s}s "
                f"(matching pids: {pids_str})"
            )
        self._launched_pid = self.gpd_pid()

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
        from gpd_tests.drivers.mcp import MCPClient

        def _ready() -> bool:
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

        ok = wait_until(_ready, timeout_s=timeout_s)
        if not ok:
            raise TimeoutError(
                "GPD did not reach a running+socket state in time"
            )
        # Rebind parent-PID tracking so sidecar_pid() matches the live tree
        # after restart/reset/manual relaunch.
        self.refresh_launched_pid()

    def wait_quit(self, *, timeout_s: float = 10.0) -> None:
        ok = wait_until(lambda: not self.is_running(), timeout_s=timeout_s)
        if not ok:
            raise TimeoutError("GPD did not quit in time")
