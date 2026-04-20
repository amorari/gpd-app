"""Session-scoped fixtures for opencode-gpd-test.

- `app_state` — launches GPD at session start, quits at session end.
- `mcp`, `http`, `ax`, `os_input` — driver instances bound to the live app.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from gpd_tests.drivers.ax import AXClient
from gpd_tests.drivers.mcp import MCPClient, MCPError
from gpd_tests.drivers.opencode_http import (
    HTTPClient,
    discover_sidecar_credentials,
    discover_sidecar_port,
)
from gpd_tests.drivers.os_input import OSInputClient
from gpd_tests.helpers import artifacts
from gpd_tests.helpers.timings import wait_until
from gpd_tests.pages.app_state import AppState


@pytest.fixture(scope="session", autouse=True)
def seed_onboarding_state(request):
    """Seed auth.json + onboarding sentinel so GPD doesn't first-run.

    Opt in via two env vars together:
      GPD_TEST_SEED_ONBOARDING=1  AND  GPD_TEST_ANTHROPIC_KEY=<key>

    The two-flag guard avoids accidentally clobbering a dev's real
    auth.json. When both are set, this fixture writes the key to
    `~/.local/share/opencode/auth.json` (mode 0o600) and ensures
    `~/.config/gpd/.gpd-initialized` exists, backing up and restoring
    both on teardown.
    """
    if os.environ.get("GPD_TEST_SEED_ONBOARDING") != "1":
        yield
        return
    key = os.environ.get("GPD_TEST_ANTHROPIC_KEY")
    if not key:
        yield
        return

    import json
    import shutil

    auth_path = Path.home() / ".local/share/opencode/auth.json"
    sentinel_path = Path.home() / ".config/gpd/.gpd-initialized"

    auth_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel_path.parent.mkdir(parents=True, exist_ok=True)

    auth_backup: Path | None = None
    created_sentinel = False

    if auth_path.exists():
        auth_backup = auth_path.with_suffix(".json.bak-test-session")
        shutil.copy2(auth_path, auth_backup)

    auth_path.write_text(
        json.dumps({"gpd": {"type": "api", "key": key}}) + "\n"
    )
    auth_path.chmod(0o600)

    if not sentinel_path.exists():
        sentinel_path.write_text("seeded-by-tests-gui\n")
        created_sentinel = True

    def restore():
        if auth_backup and auth_backup.exists():
            shutil.copy2(auth_backup, auth_path)
            auth_backup.unlink()
        elif auth_path.exists():
            auth_path.unlink()
        if created_sentinel and sentinel_path.exists():
            sentinel_path.unlink()

    request.addfinalizer(restore)
    yield


@pytest.fixture(scope="session")
def app_state() -> "AppState":
    state = AppState()
    # Cold-start mode: kill any stale GPD/opencode-cli before launching. Opt
    # in via PYTEST_COLD_START=1 so local interactive runs don't clobber the
    # user's live session.
    if os.environ.get("PYTEST_COLD_START") == "1":
        state.kill_stale()
    if not state.is_running():
        state.launch()
    state.wait_launched()
    yield state
    if os.environ.get("PYTEST_QUIT_GPD") == "1":
        state.quit()
        state.wait_quit()


@pytest.fixture
def mcp(app_state) -> MCPClient:
    client = MCPClient()
    try:
        client.ping()
    except MCPError as e:
        msg = str(e).lower()
        if not ("auth" in msg or "token" in msg or "unauthoriz" in msg):
            raise
        from scripts.discover_mcp_token import discover as discover_token

        token = discover_token()
        if not token:
            pytest.fail(
                f"MCP ping rejected as unauthenticated ({e}) and "
                "scripts/discover_mcp_token found no token. Set "
                "GPD_MCP_AUTH_TOKEN or drop a token at "
                "~/Library/Application Support/inc.psi.gpd/mcp-auth.token."
            )
        client = MCPClient(auth_token=token)
        client.ping()
    return client


@pytest.fixture
def ax(app_state) -> AXClient:
    # No eager activate() — that would steal focus from the caller. Driver
    # methods that need window focus (main_window, click_menu_item) call
    # activate() themselves; menu queries work backgrounded.
    return AXClient()


@pytest.fixture
def http(app_state) -> HTTPClient:
    def _sidecar_ready() -> bool:
        return app_state.sidecar_pid() is not None

    wait_until(_sidecar_ready, timeout_s=15.0)
    pid = app_state.sidecar_pid()
    assert pid is not None, "opencode-cli sidecar never appeared"
    port = discover_sidecar_port(pid=pid)
    user, pw = discover_sidecar_credentials(pid)
    client = HTTPClient(
        base_url=f"http://127.0.0.1:{port}",
        username=user,
        password=pw,
    )
    # MCP readiness != HTTP readiness: the sidecar can be listening on TCP
    # before /global/health wires up. Probe explicitly before handing the
    # client to tests.
    def _http_ready() -> bool:
        try:
            client.health()
            return True
        except Exception:
            return False

    if not wait_until(_http_ready, timeout_s=15.0):
        client.close()
        pytest.fail(
            f"opencode-cli sidecar at 127.0.0.1:{port} did not answer "
            "/global/health within 15s"
        )
    yield client
    client.close()


@pytest.fixture(scope="session")
def os_input() -> OSInputClient:
    return OSInputClient()


# --- Marker-driven reset hook -------------------------------------------


def pytest_runtest_setup(item):
    """Honor @pytest.mark.tier(n) / @pytest.mark.fresh_app before each test.

    fresh_app is an alias for tier(2). When a reset is requested we stop GPD,
    wipe the requested tier's paths, restart (backgrounded), and invalidate
    the session-scoped driver fixtures so they rebuild against the fresh app.
    """
    tier_marker = item.get_closest_marker("tier")
    fresh = item.get_closest_marker("fresh_app") is not None
    tier: int | None = None
    if tier_marker is not None and tier_marker.args:
        tier = int(tier_marker.args[0])
    if fresh and tier is None:
        tier = 2
    if tier is None:
        return
    import scripts.reset as reset

    reset.run(tier=tier, dry_run=False, stop_app=True, start_app=True)
    # Let the fresh app come up before the next fixture use. The driver
    # fixtures below are function-scoped so they rediscover socket path,
    # HTTP port, and creds on the next test.
    fresh = AppState()
    fresh.wait_launched(timeout_s=20.0)
    # Refresh the session-scoped app_state fixture's _launched_pid so that
    # sidecar_pid() keeps tracking the live process tree instead of a stale
    # PID from before the reset.
    try:
        session_app_state = item._request.getfixturevalue("app_state")
        session_app_state.refresh_launched_pid()
    except Exception:
        # Fixture not yet created or request not available; the first test
        # that uses app_state will see the fresh state naturally.
        pass


# --- Reporting hooks -----------------------------------------------------


def pytest_runtest_makereport(item, call):
    """Capture artifacts on test failure."""
    if call.when != "call" or call.excinfo is None:
        return
    try:
        mcp_client = item.funcargs.get("mcp")
    except Exception:
        mcp_client = None
    module = item.nodeid.split("::")[0].replace("/", "_").replace(".py", "")
    test = item.name.replace("[", "_").replace("]", "")
    d = artifacts.artifact_dir(module, test)
    # Use MCP for both screenshot and window metadata — AX window queries
    # would activate GPD and steal focus from the developer on every failure.
    if mcp_client is not None:
        try:
            artifacts.save_bytes(
                d, "screenshot.jpg", mcp_client.take_screenshot_bytes()
            )
        except Exception as e:
            artifacts.save_text(d, "screenshot.err", str(e))
        try:
            artifacts.save_json(d, "windows.json", mcp_client.list_windows())
        except Exception as e:
            artifacts.save_text(d, "windows.err", str(e))
    artifacts.save_text(d, "nodeid.txt", item.nodeid + "\n")


def pytest_report_header(config):
    slowmo = os.environ.get("PYTEST_SLOWMO_MS", "(default)")
    ci = os.environ.get("PYTEST_CI", "0")
    return [f"opencode-gpd-test | slow-mo={slowmo}ms | CI={ci}"]
