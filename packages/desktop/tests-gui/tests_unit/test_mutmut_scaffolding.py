"""Smoke test for mutmut scaffolding (G7.3).

We only confirm the dev dependency is installed and importable, plus that
the config file + wrapper script are in place. Actual mutation runs are
executed out-of-band via `scripts/run_mutation_test.sh` in a dedicated CI
job — never in the unit suite.
"""
from __future__ import annotations

import importlib
import os
import stat
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# Repo layout: tests_unit/ sits next to mutmut_config.py and scripts/.
_PKG_ROOT = Path(__file__).resolve().parent.parent


def test_mutmut_imports_cleanly() -> None:
    """mutmut must be importable when the dev extras are installed.

    Skipped on a base ``uv sync`` install (no ``--extra dev``). Unit tests
    should not force contributors to pull mutation-testing tooling just to
    run the fast suite; the dedicated ``scripts/run_mutation_test.sh``
    wrapper still requires the dev extras at invocation time.
    """
    pytest.importorskip("mutmut")
    mod = importlib.import_module("mutmut")
    # Sanity: the module object has a name. We don't assert on version/shape
    # because mutmut's public surface drifts across majors.
    assert mod.__name__ == "mutmut"


def test_mutmut_config_file_present() -> None:
    cfg = _PKG_ROOT / "mutmut_config.py"
    assert cfg.is_file(), f"missing mutmut config at {cfg}"
    text = cfg.read_text(encoding="utf-8")
    # Config must declare the runner + tests_dir so mutmut picks them up.
    assert "runner" in text
    assert "tests_dir" in text


def test_run_mutation_test_script_is_executable() -> None:
    script = _PKG_ROOT / "scripts" / "run_mutation_test.sh"
    assert script.is_file(), f"missing wrapper at {script}"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "run_mutation_test.sh must be executable"
    body = script.read_text(encoding="utf-8")
    assert "mutmut run" in body
    assert "--paths-to-mutate" in body


def test_script_rejects_missing_arg(tmp_path: Path) -> None:
    """The wrapper should exit non-zero when no target is given.

    We invoke via /bin/bash directly so this works even if the shebang
    interpreter differs on the CI runner.
    """
    import subprocess

    script = _PKG_ROOT / "scripts" / "run_mutation_test.sh"
    proc = subprocess.run(
        ["/bin/bash", str(script)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PATH": os.environ.get("PATH", "")},
    )
    assert proc.returncode != 0
    assert "Usage" in proc.stderr
