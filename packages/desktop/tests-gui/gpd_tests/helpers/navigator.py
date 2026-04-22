"""Drive GPD route changes via MCP navigate + URL polling."""
from __future__ import annotations

import base64
import time
from typing import Protocol, runtime_checkable
from urllib.parse import parse_qsl, urlparse


BASE = "tauri://localhost"

# In Tauri debug builds (cfg(dev) = true, devUrl = http://localhost:1420),
# navigating from the devUrl origin to tauri:// permanently breaks the Tauri
# IPC bridge: initialization scripts are injected only for the devUrl domain
# and are NOT re-injected on cross-protocol navigation. Translate tauri://
# navigation targets to the dev server equivalent when the webview is on the
# dev server so the bridge stays alive.
_DEV_SERVER_BASE = "http://localhost:1420"


def encode_dir_token(path: str) -> str:
    """Route token for `/:dir`: base64url of the filesystem path, no padding."""
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode().rstrip("=")


def route_home() -> str:
    return f"{BASE}/"


def route_loading() -> str:
    """Return the /loading URL string.

    .. warning::
        ``/loading`` is a *transient* state — the SPA renders it briefly while
        deciding which real route to mount.  Callers MUST NOT wait for
        ``current_url() == route_loading()``; the URL may never be observable
        via polling.  Use this value only as a *sentinel* (e.g. "if the current
        URL is still /loading, keep waiting").
    """
    return f"{BASE}/loading"


def route_project(path: str) -> str:
    return f"{BASE}/{encode_dir_token(path)}"


def route_session(session_id: str | None = None) -> str:
    """Return a bare ``/session`` or ``/session/<id>`` URL.

    .. deprecated::
        The SPA no longer exposes top-level ``/session`` routes.  Real routes
        live under ``/:dir/session/:id?``.  Use :func:`route_session_in_project`
        instead.  This function will be removed in a future release.
    """
    if session_id is None:
        return f"{BASE}/session"
    return f"{BASE}/session/{session_id}"


def route_session_in_project(dir_token: str, session_id: str | None = None) -> str:
    """Return the correct nested session URL: ``/<dir_token>/session[/<id>]``.

    Parameters
    ----------
    dir_token:
        The base64url directory token produced by :func:`encode_dir_token`.
    session_id:
        Optional session UUID.  Omit to get the session-list URL for the project.
    """
    if session_id is None:
        return f"{BASE}/{dir_token}/session"
    return f"{BASE}/{dir_token}/session/{session_id}"


def _urls_match(a: str, b: str) -> bool:
    """Compare two URLs tolerantly.

    - Trailing slashes on the path are stripped.
    - The hash fragment (``#...``) is ignored.
    - Query params are compared order-insensitively (as a multiset of
      ``(key, value)`` tuples).
    - If either URL fails to parse, fall back to a plain string compare.
    """
    try:
        pa = urlparse(a)
        pb = urlparse(b)
    except ValueError:
        return a == b

    def _norm(p):
        path = p.path.rstrip("/")
        # parse_qsl preserves duplicates; frozenset-of-counts would be more
        # correct, but for route URLs duplicate keys are vanishingly rare.
        # A sorted tuple gives order-insensitive equality.
        qs = tuple(sorted(parse_qsl(p.query, keep_blank_values=True)))
        return (p.scheme, p.netloc, path, qs)

    return _norm(pa) == _norm(pb)


@runtime_checkable
class _MCPLike(Protocol):
    def navigate(self, url: str, *, window_label: str = "main") -> None: ...
    def current_url(self, *, window_label: str = "main") -> str: ...


def _adapt_url_for_dev(current_url: str, target_url: str) -> str:
    """Translate tauri://localhost URLs to dev server equivalent when on devUrl.

    If the webview is currently on http://localhost:1420 (the Tauri devUrl)
    and the target uses the tauri:// scheme, replace the origin so the
    navigation stays within the same protocol. This preserves the Tauri IPC
    bridge initialization scripts which are injected per-origin in cfg(dev)
    mode and are not re-injected on cross-protocol (tauri:// ↔ http://)
    navigations.
    """
    if not target_url.startswith("tauri://localhost"):
        return target_url
    if not current_url.startswith(_DEV_SERVER_BASE):
        return target_url
    path = target_url[len("tauri://localhost"):]
    return f"{_DEV_SERVER_BASE}{path or '/'}"


def _same_origin(url_a: str, url_b: str) -> bool:
    """Return True if both URLs share the same scheme+host+port."""
    try:
        pa = urlparse(url_a)
        pb = urlparse(url_b)
        return pa.scheme == pb.scheme and pa.netloc == pb.netloc
    except Exception:
        return False


class Navigator:
    def __init__(self, mcp: _MCPLike) -> None:
        self._mcp = mcp

    def go(self, url: str, *, timeout_s: float = 5.0, poll_s: float = 0.1) -> None:
        """Navigate and wait for current_url to match (ignoring trailing slashes/query/hash).

        Uses SPA navigation (history.pushState + popstate) when the webview is
        already on the same origin as the target URL. This avoids a full page
        reload which breaks the Tauri awaitInitialization IPC command in cfg(dev)
        debug builds (the command never resolves after a reload, leaving the
        SolidJS Show gate permanently closed).
        """
        # Translate tauri:// to dev server URL if the webview is on devUrl.
        try:
            current = self._mcp.current_url()
        except Exception:
            current = ""
        nav_url = _adapt_url_for_dev(current, url)

        # Prefer SPA navigation (no page reload) when same-origin so that the
        # SolidJS app stays alive and awaitInitialization doesn't re-hang.
        navigated = False
        if _same_origin(current, nav_url):
            try:
                parsed = urlparse(nav_url)
                spa_path = parsed.path or "/"
                if parsed.query:
                    spa_path += f"?{parsed.query}"
                import json as _json
                safe_path = _json.dumps(spa_path)
                self._mcp.execute_js(  # type: ignore[attr-defined]
                    f"window.history.pushState(null,'',{safe_path});"
                    f"window.dispatchEvent(new PopStateEvent('popstate',{{state:null}}));"
                )
                navigated = True
            except Exception:
                pass
        if not navigated:
            self._mcp.navigate(nav_url)

        deadline = time.monotonic() + timeout_s
        last = ""
        while time.monotonic() < deadline:
            try:
                last = self._mcp.current_url()
            except Exception:
                last = ""
            if _urls_match(last, nav_url) or _urls_match(last, url):
                return
            time.sleep(poll_s)
        raise TimeoutError(
            f"navigate to {url} did not take effect; current={last!r}"
        )
