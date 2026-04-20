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
