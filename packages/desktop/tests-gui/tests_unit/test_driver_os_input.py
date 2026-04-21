"""Unit tests for gpd_tests.drivers.os_input.OSInputClient.

All subprocess interactions are mocked. Covers:
  - Happy paths (click, move, type_text, press_key).
  - 10s timeout path for every subprocess.run invocation → RuntimeError.
  - CalledProcessError path for every subprocess.run invocation (re-raised
    with decoded stderr).
  - Ctor guards for cliclick / osascript missing from PATH.
  - type_text unicode + empty-string + newline guard.
  - press_key coverage for every entry in _KEY_CODES + unknown-key guard.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gpd_tests.drivers.os_input import _KEY_CODES, OSInputClient


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _has_cliclick():
    """OSInputClient ctor checks cliclick + osascript on PATH; stub both."""
    with patch(
        "gpd_tests.drivers.os_input.shutil.which",
        return_value="/usr/local/bin/stub",
    ):
        yield


def _ok_run():
    """Helper: MagicMock mimicking a successful subprocess.run result."""
    return MagicMock(returncode=0, stdout="", stderr="")


# --------------------------------------------------------------------------- #
# Ctor guards                                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_ctor_raises_when_cliclick_missing():
    # `which` returns None for cliclick, a path otherwise.
    def which(name):
        return None if name == "cliclick" else "/usr/bin/osascript"

    with patch("gpd_tests.drivers.os_input.shutil.which", side_effect=which):
        with pytest.raises(RuntimeError, match="cliclick not on PATH"):
            OSInputClient()


@pytest.mark.unit
def test_ctor_raises_when_osascript_missing():
    def which(name):
        return "/usr/local/bin/cliclick" if name == "cliclick" else None

    with patch("gpd_tests.drivers.os_input.shutil.which", side_effect=which):
        with pytest.raises(RuntimeError, match="osascript not on PATH"):
            OSInputClient()


# --------------------------------------------------------------------------- #
# click()                                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_click_calls_cliclick_with_coords():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().click(120, 240)

    assert calls[0][0] == "cliclick"
    assert calls[0][1] == "c:120,240"


@pytest.mark.unit
def test_click_passes_10s_timeout():
    """Per F9, every subprocess.run must carry a 10s timeout kwarg."""
    kwargs_seen: dict = {}

    def fake_run(cmd, **kwargs):
        kwargs_seen.update(kwargs)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().click(1, 2)

    assert kwargs_seen.get("timeout") == 10
    assert kwargs_seen.get("check") is True


@pytest.mark.unit
def test_click_timeout_raises_runtime_error():
    def boom(cmd, **_):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(RuntimeError, match="timed out after 10s"):
            OSInputClient().click(10, 20)


@pytest.mark.unit
def test_click_called_process_error_reraised_with_decoded_stderr():
    def boom(cmd, **_):
        raise subprocess.CalledProcessError(
            returncode=2, cmd=cmd, output=b"", stderr=b"boom!"
        )

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            OSInputClient().click(10, 20)

    assert excinfo.value.returncode == 2
    # stderr must be decoded from bytes → str.
    assert excinfo.value.stderr == "boom!"


@pytest.mark.unit
def test_click_called_process_error_with_str_stderr_passthrough():
    """Branch: `isinstance(e.stderr, bytes)` False → use stderr as-is."""
    def boom(cmd, **_):
        raise subprocess.CalledProcessError(
            returncode=3, cmd=cmd, output="", stderr="already-str"
        )

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            OSInputClient().click(1, 2)

    assert excinfo.value.stderr == "already-str"


# --------------------------------------------------------------------------- #
# move()                                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_move_calls_cliclick_with_coords():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().move(-5, 999)

    assert calls[0] == ["cliclick", "m:-5,999"]


@pytest.mark.unit
def test_move_timeout_raises_runtime_error():
    def boom(cmd, **_):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(RuntimeError, match="timed out after 10s"):
            OSInputClient().move(0, 0)


@pytest.mark.unit
def test_move_called_process_error_reraised():
    def boom(cmd, **_):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=cmd, output=b"", stderr=b"nope"
        )

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            OSInputClient().move(1, 2)

    assert excinfo.value.stderr == "nope"


# --------------------------------------------------------------------------- #
# type_text()                                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_type_text_uses_applescript_keystroke():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().type_text('hello "world"')

    assert calls[0][0] == "osascript"
    assert '"hello \\"world\\""' in calls[0][-1]


@pytest.mark.unit
def test_type_text_escapes_backslash():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().type_text("a\\b")

    # Each backslash in input is doubled in the AppleScript string literal.
    assert "a\\\\b" in calls[0][-1]


@pytest.mark.unit
def test_type_text_unicode():
    """Unicode passes through unescaped; command must still be osascript."""
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().type_text("héllo — 你好 ✓")

    assert calls[0][0] == "osascript"
    assert "héllo — 你好 ✓" in calls[0][-1]


@pytest.mark.unit
def test_type_text_empty_string():
    """Empty string should still dispatch one osascript keystroke call."""
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().type_text("")

    assert len(calls) == 1
    assert calls[0][0] == "osascript"
    assert 'keystroke ""' in calls[0][-1]


@pytest.mark.unit
def test_type_text_rejects_newline():
    with patch("gpd_tests.drivers.os_input.subprocess.run") as run:
        with pytest.raises(ValueError, match="does not support newline"):
            OSInputClient().type_text("line1\nline2")
        run.assert_not_called()


@pytest.mark.unit
def test_type_text_rejects_carriage_return():
    with patch("gpd_tests.drivers.os_input.subprocess.run") as run:
        with pytest.raises(ValueError, match="does not support newline"):
            OSInputClient().type_text("line1\rline2")
        run.assert_not_called()


@pytest.mark.unit
def test_type_text_timeout_raises_runtime_error():
    def boom(cmd, **_):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(RuntimeError, match="timed out after 10s"):
            OSInputClient().type_text("hi")


@pytest.mark.unit
def test_type_text_called_process_error_reraised():
    def boom(cmd, **_):
        raise subprocess.CalledProcessError(
            returncode=4, cmd=cmd, output=b"", stderr=b"osa-err"
        )

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            OSInputClient().type_text("hi")

    assert excinfo.value.stderr == "osa-err"


# --------------------------------------------------------------------------- #
# press_key()                                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_press_key_applescript():
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().press_key("escape")

    assert calls[0][0] == "osascript"
    assert "key code 53" in calls[0][-1]


@pytest.mark.unit
@pytest.mark.parametrize("name,code", sorted(_KEY_CODES.items()))
def test_press_key_all_named_keys(name: str, code: int):
    """Exercise every entry in _KEY_CODES (escape/esc/return/enter/tab/space/
    delete/backspace/left/right/down/up)."""
    calls: list[list[str]] = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        return _ok_run()

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=fake_run):
        OSInputClient().press_key(name)

    assert calls[0][0] == "osascript"
    assert f"key code {code}" in calls[0][-1]


@pytest.mark.unit
def test_press_key_rejects_unknown_key():
    with patch("gpd_tests.drivers.os_input.subprocess.run") as run:
        with pytest.raises(ValueError, match="unknown key: cmd"):
            OSInputClient().press_key("cmd")
        run.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["shift", "ctrl", "option", "f1", "", "RETURN"])
def test_press_key_rejects_other_unknown_keys(bad: str):
    """Modifier names (cmd/shift/ctrl/option) are NOT supported — press_key
    only accepts entries from _KEY_CODES. Case-sensitive ('RETURN' ≠ 'return')."""
    with patch("gpd_tests.drivers.os_input.subprocess.run") as run:
        with pytest.raises(ValueError, match="unknown key"):
            OSInputClient().press_key(bad)
        run.assert_not_called()


@pytest.mark.unit
def test_press_key_timeout_raises_runtime_error():
    def boom(cmd, **_):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(RuntimeError, match="timed out after 10s"):
            OSInputClient().press_key("escape")


@pytest.mark.unit
def test_press_key_called_process_error_reraised():
    def boom(cmd, **_):
        raise subprocess.CalledProcessError(
            returncode=5, cmd=cmd, output=b"", stderr=b"ka-boom"
        )

    with patch("gpd_tests.drivers.os_input.subprocess.run", side_effect=boom):
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            OSInputClient().press_key("tab")

    assert excinfo.value.stderr == "ka-boom"
