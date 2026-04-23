from unittest.mock import patch

import pytest

from gpd_tests.helpers.sheet import has_native_sheet


@pytest.mark.unit
def test_has_native_sheet_true_when_sheet_count_positive():
    with patch("gpd_tests.helpers.sheet._osascript", return_value="1"):
        assert has_native_sheet("GPD") is True


@pytest.mark.unit
def test_has_native_sheet_false_when_zero():
    with patch("gpd_tests.helpers.sheet._osascript", return_value="0"):
        assert has_native_sheet("GPD") is False


@pytest.mark.unit
def test_has_native_sheet_false_on_error():
    def boom(_: str) -> str:
        raise RuntimeError("AX failed")

    with patch("gpd_tests.helpers.sheet._osascript", side_effect=boom):
        assert has_native_sheet("GPD") is False
