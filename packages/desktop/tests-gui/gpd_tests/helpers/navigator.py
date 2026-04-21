"""Drive GPD route changes via MCP navigate + URL polling."""
from __future__ import annotations

import base64
import time
from typing import Protocol, runtime_checkable
from urllib.parse import parse_qsl, urlparse


BASE = "tauri://localhost"


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


class Navigator:
    def __init__(self, mcp: _MCPLike) -> None:
        self._mcp = mcp

    def go(self, url: str, *, timeout_s: float = 5.0, poll_s: float = 0.1) -> None:
        """Navigate and wait for current_url to match (ignoring trailing slashes/query/hash)."""
        self._mcp.navigate(url)
        deadline = time.monotonic() + timeout_s
        last = ""
        while time.monotonic() < deadline:
            try:
                last = self._mcp.current_url()
            except Exception:
                last = ""
            if _urls_match(last, url):
                return
            time.sleep(poll_s)
        raise TimeoutError(
            f"navigate to {url} did not take effect; current={last!r}"
        )
