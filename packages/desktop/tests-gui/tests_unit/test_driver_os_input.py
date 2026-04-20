from unittest.mock import MagicMock, patch

import pytest

from gpd_tests.drivers.os_input import OSInputClient


@pytest.fixture(autouse=True)
def _has_cliclick():
    """OSInputClient ctor checks cliclick on PATH; mock it out for unit tests."""
    with patch("gpd_tests.drivers.os_input.shutil.which", return_value="/usr/local/bin/cliclick"):
        yield


@pytest.mark.unit
def test_click_calls_cliclick_with_coords():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().click(120, 240)

    assert calls[0][0] == "cliclick"
    assert calls[0][1] == "c:120,240"


@pytest.mark.unit
def test_type_text_uses_applescript_keystroke():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().type_text('hello "world"')

    assert calls[0][0] == "osascript"
    assert '"hello \\"world\\""' in calls[0][-1]


@pytest.mark.unit
def test_press_key_applescript():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().press_key("escape")

    assert calls[0][0] == "osascript"
    assert "key code 53" in calls[0][-1]
