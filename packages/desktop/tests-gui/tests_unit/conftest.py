"""Shared fixtures for unit tests. Provides a fake MCP Unix socket."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from collections.abc import Callable

import pytest


@pytest.fixture
def fake_mcp_socket():
    """Serve a single client on a temp Unix socket with a caller-supplied handler.

    Usage:
        with fake_mcp_socket(handler) as path:
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
                            resp = handler(req)
                            conn.sendall((json.dumps(resp) + "\n").encode())
                finally:
                    conn.close()

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        servers.append((srv, t, path))
        return path

    yield make

    for srv, _t, path in servers:
        srv.close()
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
