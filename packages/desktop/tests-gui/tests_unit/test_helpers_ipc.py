"""Shape-only tests for invoke_via_mcp. Validates we build the right Tauri
__TAURI_INTERNALS__.invoke() call string."""
from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.ipc import invoke_via_mcp


@pytest.mark.unit
def test_invoke_builds_correct_js():
    mcp = MagicMock()
    mcp.execute_js.return_value = '"result"'

    invoke_via_mcp(mcp, "read_project_file", {"path": "/tmp/x"})

    js = mcp.execute_js.call_args.args[0]
    assert "__TAURI_INTERNALS__.invoke" in js
    assert '"read_project_file"' in js
    assert '"/tmp/x"' in js


@pytest.mark.unit
def test_invoke_returns_parsed_json():
    mcp = MagicMock()
    mcp.execute_js.return_value = '{"ok": true, "value": 42}'

    result = invoke_via_mcp(mcp, "some_cmd", {})

    assert result == {"ok": True, "value": 42}


@pytest.mark.unit
def test_invoke_raises_on_tauri_error():
    from gpd_tests.helpers.ipc import IPCError

    mcp = MagicMock()
    mcp.execute_js.return_value = '{"__tauri_error__": "permission denied"}'

    with pytest.raises(IPCError, match="permission denied"):
        invoke_via_mcp(mcp, "cmd", {})


@pytest.mark.unit
def test_invoke_handles_null_result():
    """A command that returns undefined → JS returns "null"; caller gets None."""
    mcp = MagicMock()
    mcp.execute_js.return_value = 'null'

    result = invoke_via_mcp(mcp, "cmd", {})

    assert result is None


@pytest.mark.unit
def test_invoke_raises_on_non_json_response():
    from gpd_tests.helpers.ipc import IPCError

    mcp = MagicMock()
    mcp.execute_js.return_value = "not json at all {"

    with pytest.raises(IPCError, match="non-JSON"):
        invoke_via_mcp(mcp, "cmd", {})


@pytest.mark.unit
def test_invoke_passes_window_label_kwarg():
    mcp = MagicMock()
    mcp.execute_js.return_value = '"ok"'

    invoke_via_mcp(mcp, "cmd", {}, window_label="secondary")

    assert mcp.execute_js.call_args.kwargs["window_label"] == "secondary"
