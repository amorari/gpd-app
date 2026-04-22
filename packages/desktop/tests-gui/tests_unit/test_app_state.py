from unittest.mock import patch

import pytest

from gpd_tests.pages.app_state import AppState, _PGREP_PATTERN


@pytest.mark.unit
def test_is_running_checks_pgrep():
    with patch("gpd_tests.pages.app_state.subprocess.run") as run:
        # ps -ax -o pid=,command= output: "PID command" per line
        run.return_value.stdout = f"11119 {_PGREP_PATTERN}GPD\n"
        run.return_value.returncode = 0
        assert AppState().is_running() is True


@pytest.mark.unit
def test_is_running_false_when_pgrep_empty():
    with patch("gpd_tests.pages.app_state.subprocess.run") as run:
        run.return_value.stdout = ""
        run.return_value.returncode = 0
        assert AppState().is_running() is False
