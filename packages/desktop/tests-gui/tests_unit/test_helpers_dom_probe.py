from unittest.mock import MagicMock

import pytest

from gpd_tests.drivers.mcp import MCPError, MCPTimeout
from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


@pytest.mark.unit
def test_probe_returns_stringified_result_when_bridge_works():
    mcp = MagicMock()
    mcp.execute_js.return_value = "42"
    assert DOMProbe(mcp).eval("1+1") == "42"


@pytest.mark.unit
def test_probe_raises_probeskip_on_timeout():
    mcp = MagicMock()
    mcp.execute_js.side_effect = MCPTimeout("empty response")
    with pytest.raises(ProbeSkip):
        DOMProbe(mcp).eval("x")


@pytest.mark.unit
def test_probe_raises_probeskip_on_timeout_error_message():
    mcp = MagicMock()
    mcp.execute_js.side_effect = MCPError("Timeout waiting for JS execution")
    with pytest.raises(ProbeSkip):
        DOMProbe(mcp).eval("x")


@pytest.mark.unit
def test_probe_reraises_other_mcperrors():
    mcp = MagicMock()
    mcp.execute_js.side_effect = MCPError("syntax error")
    with pytest.raises(MCPError):
        DOMProbe(mcp).eval("x")


@pytest.mark.unit
def test_probe_eval_bool_parses_truthy_strings():
    mcp = MagicMock()
    probe = DOMProbe(mcp)
    for v in ("true", True, "True"):
        mcp.execute_js.return_value = v
        assert probe.eval_bool("x") is True
    for v in ("false", False, "False", "null", ""):
        mcp.execute_js.return_value = v
        assert probe.eval_bool("x") is False


@pytest.mark.unit
def test_eval_bool_handles_js_falsy_strings():
    """JS falsy string representations must all evaluate to False."""
    mcp = MagicMock()
    probe = DOMProbe(mcp)
    # All of these are falsy in JavaScript — eval_bool must return False.
    for falsy_val in ("false", "0", "null", "undefined", "NaN", ""):
        mcp.execute_js.return_value = falsy_val
        result = probe.eval_bool("someExpr")
        assert result is False, (
            f"eval_bool({falsy_val!r}) returned {result!r}; expected False"
        )


@pytest.mark.unit
def test_eval_bool_handles_js_truthy_strings():
    """'true' and True must evaluate to True; 'false' must remain False."""
    mcp = MagicMock()
    probe = DOMProbe(mcp)
    # Canonical truthy values.
    for truthy_val in ("true", True):
        mcp.execute_js.return_value = truthy_val
        result = probe.eval_bool("someExpr")
        assert result is True, (
            f"eval_bool({truthy_val!r}) returned {result!r}; expected True"
        )
    # Boolean False must round-trip correctly.
    mcp.execute_js.return_value = False
    assert probe.eval_bool("x") is False


@pytest.mark.unit
def test_eval_returns_none_when_execute_js_returns_none():
    """eval() passes through None from execute_js without raising ProbeSkip.

    If the server returns empty data (None), eval() returns None. Callers
    that need to handle None as a skip condition should use eval_bool() or
    check the return value explicitly.
    """
    mcp = MagicMock()
    mcp.execute_js.return_value = None
    result = DOMProbe(mcp).eval("document.title")
    # None is passed through — no exception raised.
    assert result is None


@pytest.mark.unit
def test_eval_bool_returns_false_when_execute_js_returns_none():
    """eval_bool() converts None to False via bool()."""
    mcp = MagicMock()
    mcp.execute_js.return_value = None
    result = DOMProbe(mcp).eval_bool("document.querySelector('#x') !== null")
    assert result is False
