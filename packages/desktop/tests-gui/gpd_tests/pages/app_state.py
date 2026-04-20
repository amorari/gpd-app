"""GPD application-lifecycle helpers."""
from __future__ import annotations

import os
import subprocess

from gpd_tests.drivers.mcp import _discover_socket_path
from gpd_tests.helpers.timings import wait_until

def _default_app_path() -> str:
    """Resolve GPD.app.

    Order: GPD_APP_PATH env override > installed /Applications/GPD.app.
    In-tree dev builds land at
    packages/desktop/src-tauri/target/{debug,release}/bundle/macos/GPD.app —
    point GPD_APP_PATH there when running against a local build.
    """
    return os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")


APP_PATH = _default_app_path()


def _pgrep(pattern: str) -> list[int]:
    out = subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    return [int(x) for x in out.stdout.split() if x.strip().isdigit()]


class AppState:
    def __init__(self) -> None:
        self._launched_pid: int | None = None

    def is_running(self) -> bool:
        return bool(_pgrep("GPD.app/Contents/MacOS/GPD"))

    def gpd_pid(self) -> int | None:
        pids = _pgrep("GPD.app/Contents/MacOS/GPD")
        return pids[0] if pids else None

    def sidecar_pid(self) -> int | None:
        """Return the opencode-cli serve pid.

        When this AppState launched GPD, prefer the sidecar whose parent is
        our launched GPD process — avoids attaching to a stale unrelated
        opencode-cli instance. Falls back to first-match if parent lookup
        fails.
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
        return pids[0]

    def kill_stale(self) -> None:
        """Terminate any leftover GPD / opencode-cli processes."""
        for pattern in ("GPD.app/Contents/MacOS/GPD", "opencode-cli.*serve"):
            for pid in _pgrep(pattern):
                subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    capture_output=True,
                    check=False,
                )
        wait_until(
            lambda: not _pgrep("GPD.app/Contents/MacOS/GPD")
            and not _pgrep("opencode-cli.*serve"),
            timeout_s=5.0,
        )

    def launch(self, *, background: bool = True) -> None:
        """Launch GPD. Default is background (-g) — keeps focus on the
        caller's current app. Pass background=False to bring GPD frontmost.
        """
        args = ["open", "-a", APP_PATH]
        if background:
            args.insert(1, "-g")
        subprocess.run(args, check=True)
        wait_until(lambda: self.is_running(), timeout_s=10.0)
        self._launched_pid = self.gpd_pid()

    def quit(self) -> None:
        subprocess.run(
            ["osascript", "-e", 'tell application "GPD" to quit'],
            capture_output=True,
            check=False,
        )
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
