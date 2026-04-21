"""HTTP client for opencode-cli sidecar API."""
from __future__ import annotations

import subprocess
from typing import Any

import httpx


class HTTPClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            auth=(username, password),
            transport=transport,
            timeout=timeout_s,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HTTPClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str) -> Any:
        r = self._client.get(path)
        r.raise_for_status()
        return r.json()

    def health(self) -> dict[str, Any]:
        return self._get("/global/health")

    def sessions(self, *, directory: str | None = None) -> list[dict[str, Any]]:
        if directory is not None:
            r = self._client.get("/session", params={"directory": directory})
            r.raise_for_status()
            return r.json()
        return self._get("/session")

    def providers(self) -> dict[str, Any]:
        return self._get("/config/providers")

    def path_info(self) -> dict[str, Any]:
        return self._get("/path")

    def _post(self, path: str, json: dict | list | None = None, params: dict | None = None) -> Any:
        r = self._client.post(path, json=json, params=params)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        ct = r.headers.get("content-type", "")
        if "json" in ct or r.text.startswith(("{", "[")):
            return r.json()
        return r.text

    def _delete(self, path: str) -> Any:
        r = self._client.delete(path)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    def create_session(
        self,
        *,
        directory: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if parent_id is not None:
            body["parentID"] = parent_id
        params = {"directory": directory} if directory is not None else None
        return self._post("/session", json=body, params=params)

    def send_message(
        self,
        session_id: str,
        *,
        parts: list[dict[str, Any]],
        model_id: str | None = None,
        provider_id: str | None = None,
        agent: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"parts": parts}
        if (model_id is None) != (provider_id is None):
            raise ValueError("model_id and provider_id must be provided together")
        if model_id is not None and provider_id is not None:
            body["model"] = {"modelID": model_id, "providerID": provider_id}
        if agent is not None:
            body["agent"] = agent
        return self._post(f"/session/{session_id}/message", json=body)

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        return self._get(f"/session/{session_id}/message")

    def delete_session(self, session_id: str) -> bool:
        r = self._delete(f"/session/{session_id}")
        return r is None or bool(r)


def discover_sidecar_port(
    *, pid: int | None = None, timeout_s: float = 15.0
) -> int:
    """Return the TCP port opencode-cli listens on.

    Retries up to `timeout_s`. If a `pid` was passed, re-validate it each
    attempt: a crashed-then-respawned sidecar has a new PID, so we must
    rediscover instead of hammering a dead one.
    """
    import time

    deadline = time.monotonic() + timeout_s
    last_err: str = ""
    probe_pid = pid
    while time.monotonic() < deadline:
        if probe_pid is not None and not _pid_alive(probe_pid):
            probe_pid = None  # force rediscovery on next iteration
        try:
            return _probe_port_once(pid=probe_pid)
        except RuntimeError as e:
            last_err = str(e)
            probe_pid = None  # rediscover PID in case sidecar respawned
            time.sleep(0.25)
    raise RuntimeError(f"no listening port after {timeout_s}s: {last_err}")


def _pid_alive(pid: int) -> bool:
    try:
        os_kill = subprocess.run(
            ["kill", "-0", str(pid)],
            capture_output=True,
            check=False,
        )
        return os_kill.returncode == 0
    except Exception:
        return False


def _probe_port_once(*, pid: int | None) -> int:
    if pid is None:
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        if not pids:
            raise RuntimeError("opencode-cli not running")
        pid = pids[0]
    # -a ANDs the filters; without it lsof returns every listening socket on
    # the system, so the first 127.0.0.1:... line may belong to a completely
    # unrelated process.
    out = subprocess.run(
        ["lsof", "-a", "-P", "-n", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in out.stdout.splitlines():
        if "127.0.0.1:" in line:
            port = line.rsplit("127.0.0.1:", 1)[1].split(" ", 1)[0]
            port = port.split("(")[0].strip()
            return int(port)
    raise RuntimeError(f"no listening port found for pid {pid}")


def discover_sidecar_credentials(pid: int) -> tuple[str, str]:
    """Read OPENCODE_SERVER_USERNAME/PASSWORD from the sidecar process env.

    Uses `ps -E -p <pid>` which, on macOS, prints the env for same-user processes.
    """
    out = subprocess.run(
        ["ps", "-E", "-ww", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    env_text = out.stdout
    user = _extract_env(env_text, "OPENCODE_SERVER_USERNAME") or "opencode"
    pw = _extract_env(env_text, "OPENCODE_SERVER_PASSWORD")
    if not pw:
        raise RuntimeError("OPENCODE_SERVER_PASSWORD not found in sidecar env")
    return user, pw


def _extract_env(blob: str, key: str) -> str | None:
    token = f" {key}="
    idx = blob.find(token)
    if idx == -1:
        return None
    start = idx + len(token)
    end = blob.find(" ", start)
    if end == -1:
        end = len(blob)
    return blob[start:end]
