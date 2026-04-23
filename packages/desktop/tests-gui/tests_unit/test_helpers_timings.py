import time

import pytest

from gpd_tests.helpers import timings


@pytest.mark.unit
def test_slowmo_returns_env_value_in_ms(monkeypatch):
    monkeypatch.setenv("PYTEST_SLOWMO_MS", "50")
    assert timings.slowmo_ms() == 50


@pytest.mark.unit
def test_slowmo_defaults_to_200_locally_and_0_in_ci(monkeypatch):
    monkeypatch.delenv("PYTEST_SLOWMO_MS", raising=False)
    monkeypatch.delenv("PYTEST_CI", raising=False)
    assert timings.slowmo_ms() == 200
    monkeypatch.setenv("PYTEST_CI", "1")
    assert timings.slowmo_ms() == 0


@pytest.mark.unit
def test_wait_until_returns_true_when_predicate_passes():
    deadline = time.monotonic() + 0.3
    calls = {"n": 0}

    def pred() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    assert timings.wait_until(pred, timeout_s=1.0, poll_s=0.01)
    assert time.monotonic() < deadline + 0.5


@pytest.mark.unit
def test_wait_until_returns_false_on_timeout():
    start = time.monotonic()
    assert not timings.wait_until(lambda: False, timeout_s=0.1, poll_s=0.02)
    assert time.monotonic() - start >= 0.1
