"""Shared fixtures for unit tests. Provides a fake MCP Unix socket."""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import traceback
from collections.abc import Callable

import pytest


@pytest.fixture
def fake_mcp_socket():
    """Serve a single client on a temp Unix socket with a caller-supplied handler.

    Usage:
        path = fake_mcp_socket(handler)
        client = MCPClient(socket_path=str(path))
        ...
    """
    servers: list[tuple[socket.socket, threading.Thread, str]] = []

    def make(handler: Callable[[dict], dict]):
        tmpdir = tempfile.mkdtemp(prefix="mcpfake_")
        path = os.path.join(tmpdir, "sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(4)
        srv.settimeout(5.0)

        def loop() -> None:
            while True:
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                try:
                    conn.settimeout(5.0)
                    buf = b""
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            if not line.strip():
                                continue
                            req = json.loads(line.decode())
                            try:
                                resp = handler(req)
                            except Exception as exc:
                                # Handler exceptions must not silently kill the
                                # server thread — send an error response so the
                                # client gets a meaningful failure, and print the
                                # traceback to stderr for easier debugging.
                                traceback.print_exc(file=sys.stderr)
                                resp = {
                                    "success": False,
                                    "data": None,
                                    "error": repr(exc),
                                    "id": req.get("id", ""),
                                }
                            conn.sendall((json.dumps(resp) + "\n").encode())
                finally:
                    conn.close()

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        servers.append((srv, t, path))
        return path

    yield make

    for srv, t, path in servers:
        srv.close()
        t.join(timeout=2.0)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        try:
            os.rmdir(os.path.dirname(path))
        except OSError:
            pass
