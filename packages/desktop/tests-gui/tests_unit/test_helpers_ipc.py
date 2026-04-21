"""Shape-only tests for invoke_via_mcp (slot-poll variant).

The helper submits an async statement that stashes its result on
`window.__gpd_ipc_slot_*`, then polls that slot via subsequent `execute_js`
calls until settled. The tests verify the wire shape (JS content) and the
poll/settle/error semantics using a MagicMock for `execute_js`.
"""
from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


def _mcp_with_script(script):
    """Return a MagicMock whose `execute_js` returns values from `script`.

    `script` is a list of strings; each call consumes one. Once exhausted,
    returns the last value (useful for the stable-poll case).
    """
    mcp = MagicMock()
    iterator = iter(script)
    last = script[-1]

    def _exec(js, window_label="main"):
        nonlocal last
        try:
            v = next(iterator)
            last = v
            return v
        except StopIteration:
            return last

    mcp.execute_js.side_effect = _exec
    return mcp


@pytest.mark.unit
def test_invoke_submits_tauri_invoke_call_string():
    mcp = _mcp_with_script([
        "null",  # submit (returns null, per submit_js's `return null;`)
        '{"ok":true,"value":"result"}',  # poll settles immediately
        "null",  # cleanup
    ])
    invoke_via_mcp(mcp, "read_project_file", {"path": "/tmp/x"}, deadline_s=1.0)
    submit_js = mcp.execute_js.call_args_list[0].args[0]
    assert "__TAURI_INTERNALS__.invoke" in submit_js
    assert '"read_project_file"' in submit_js
    assert '"/tmp/x"' in submit_js


@pytest.mark.unit
def test_invoke_polls_until_slot_settles():
    mcp = _mcp_with_script([
        "null",                                 # submit
        "null",                                 # poll 1: still pending
        "null",                                 # poll 2: still pending
        '{"ok":true,"value":42}',              # poll 3: settled
        "null",                                 # cleanup
    ])
    result = invoke_via_mcp(mcp, "cmd", {}, deadline_s=2.0, poll_interval_s=0.01)
    assert result == 42
    # Submit + 3 polls + cleanup = 5 execute_js calls
    assert mcp.execute_js.call_count == 5


@pytest.mark.unit
def test_invoke_returns_none_when_value_is_null():
    mcp = _mcp_with_script([
        "null",
        '{"ok":true,"value":null}',
        "null",
    ])
    assert invoke_via_mcp(mcp, "cmd", {}, deadline_s=1.0) is None


@pytest.mark.unit
def test_invoke_raises_on_err_slot():
    mcp = _mcp_with_script([
        "null",
        '{"ok":false,"err":"permission denied"}',
        "null",
    ])
    with pytest.raises(IPCError, match="permission denied"):
        invoke_via_mcp(mcp, "cmd", {}, deadline_s=1.0)


@pytest.mark.unit
def test_invoke_still_recognizes_legacy_tauri_error_shape():
    """Back-compat: a slot that reports {__tauri_error__: "..."} is accepted."""
    mcp = _mcp_with_script([
        "null",
        '{"__tauri_error__":"old-shape error"}',
        "null",
    ])
    with pytest.raises(IPCError, match="old-shape error"):
        invoke_via_mcp(mcp, "cmd", {}, deadline_s=1.0)


@pytest.mark.unit
def test_invoke_raises_on_non_json_poll_response():
    mcp = _mcp_with_script([
        "null",
        "not json at all {",  # malformed poll
    ])
    with pytest.raises(IPCError, match="non-JSON"):
        invoke_via_mcp(mcp, "cmd", {}, deadline_s=1.0)


@pytest.mark.unit
def test_invoke_raises_on_deadline_expiry():
    """If the slot never settles, the helper raises IPCError, never hangs."""
    mcp = _mcp_with_script(["null", "null", "null", "null", "null"])
    with pytest.raises(IPCError, match="did not settle"):
        invoke_via_mcp(mcp, "cmd", {}, deadline_s=0.2, poll_interval_s=0.05)


@pytest.mark.unit
def test_invoke_passes_window_label_kwarg_to_submit_and_poll():
    mcp = _mcp_with_script([
        "null",
        '{"ok":true,"value":"x"}',
        "null",
    ])
    invoke_via_mcp(mcp, "cmd", {}, window_label="secondary", deadline_s=1.0)
    for call in mcp.execute_js.call_args_list:
        assert call.kwargs["window_label"] == "secondary"


@pytest.mark.unit
def test_invoke_clears_slot_after_settling():
    mcp = _mcp_with_script([
        "null",
        '{"ok":true,"value":"x"}',
        "null",
    ])
    invoke_via_mcp(mcp, "cmd", {}, deadline_s=1.0)
    cleanup_js = mcp.execute_js.call_args_list[-1].args[0]
    assert "delete window[" in cleanup_js
