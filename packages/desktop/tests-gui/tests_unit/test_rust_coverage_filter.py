"""Unit tests for the rust_coverage_filter.sh parsing/rendering layer.

We don't invoke ``cargo llvm-cov`` from unit tests (too slow, requires Rust
toolchain + llvm-tools). Instead we exercise the Python implementation module
directly with a synthesized JSON export that mimics cargo-llvm-cov's shape.

We also drive the shell script end-to-end via ``COV_JSON_PATH`` (which skips
the cargo invocation) to verify the script wires CLI args through to the
parser correctly.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the implementation module directly from its on-disk path: the file
# lives under src-tauri/scripts/, which is outside the tests-gui package, so
# we can't rely on normal sys.path import resolution.
# ---------------------------------------------------------------------------
# tests-gui/tests_unit/foo.py → parents[0]=tests_unit, [1]=tests-gui, [2]=desktop
_DESKTOP_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIR = _DESKTOP_ROOT / "src-tauri" / "scripts"
_IMPL_PATH = _SCRIPT_DIR / "_cov_filter_impl.py"
_SHELL_PATH = _SCRIPT_DIR / "rust_coverage_filter.sh"


def _load_impl():
    spec = importlib.util.spec_from_file_location(
        "_cov_filter_impl", _IMPL_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def impl():
    return _load_impl()


def _fake_llvm_cov_json() -> dict:
    """Minimal cargo-llvm-cov JSON export with three functions so we can
    assert matching picks the right ones and skips the rest."""
    return {
        "data": [
            {
                "files": [],
                "functions": [
                    {
                        "name": "opencode_lib::project_fs::check_project_accessible::h1234",
                        "filenames": [
                            "/repo/packages/desktop/src-tauri/src/project_fs.rs"
                        ],
                        "summary": {
                            "lines": {"covered": 8, "count": 10, "percent": 80.0}
                        },
                    },
                    {
                        "name": "opencode_lib::project_fs::create_project::h5678",
                        "filenames": [
                            "/repo/packages/desktop/src-tauri/src/project_fs.rs"
                        ],
                        "summary": {
                            "lines": {"covered": 0, "count": 0, "percent": 0.0}
                        },
                    },
                    {
                        "name": "opencode_lib::tex_compiler::compile_tex::habcd",
                        "filenames": [
                            "/repo/packages/desktop/src-tauri/src/tex_compiler.rs"
                        ],
                        "summary": {
                            "lines": {"covered": 3, "count": 12, "percent": 25.0}
                        },
                    },
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# name_matches heuristics
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_name_matches_path_segment(impl):
    assert impl.name_matches(
        "opencode_lib::project_fs::check_project_accessible::h1234",
        "check_project_accessible",
    )


@pytest.mark.unit
def test_name_matches_no_hash_suffix(impl):
    assert impl.name_matches(
        "opencode_lib::project_fs::check_project_accessible",
        "check_project_accessible",
    )


@pytest.mark.unit
def test_name_matches_tauri_dispatcher_wrapper(impl):
    assert impl.name_matches(
        "opencode_lib::__cmd__check_project_accessible", "check_project_accessible"
    )


@pytest.mark.unit
def test_name_matches_exact(impl):
    assert impl.name_matches("check_project_accessible", "check_project_accessible")


@pytest.mark.unit
def test_name_matches_rejects_unrelated(impl):
    assert not impl.name_matches(
        "opencode_lib::project_fs::create_project::h5678",
        "check_project_accessible",
    )
    assert not impl.name_matches("", "check_project_accessible")
    assert not impl.name_matches("anything", "")


@pytest.mark.unit
def test_name_matches_avoids_substring_false_positive(impl):
    # "check_project" is a prefix of "check_project_accessible" but should
    # not match the longer name.
    assert not impl.name_matches(
        "opencode_lib::project_fs::check_project_accessible::h1",
        "check_project",
    )


@pytest.mark.unit
def test_name_matches_rust_v0_mangling(impl):
    # Real-world sample from cargo-llvm-cov on a Homebrew-Rust box. The v0
    # mangled form encodes each component as ``<len><name>`` with no
    # delimiter; ``24check_project_accessible`` is the project_fs component.
    assert impl.name_matches(
        "_RNvNtCs8EFNFryo1kC_12opencode_lib10project_fs24check_project_accessible",
        "check_project_accessible",
    )


@pytest.mark.unit
def test_name_matches_v0_rejects_longer_component(impl):
    # v0: the function is actually `check_project_accessible` (length 24).
    # Searching for `check_project` (length 13) must NOT match because the
    # encoded prefix is `24` not `13`, and our length-aware regex enforces
    # that.
    assert not impl.name_matches(
        "_RNvNtCs8EFNFryo1kC_12opencode_lib10project_fs24check_project_accessible",
        "check_project",
    )


@pytest.mark.unit
def test_name_matches_v0_rejects_different_component(impl):
    # create_project_directory must not match when we're looking for
    # create_project (would need `14create_project` but we have
    # `24create_project_directory`).
    assert not impl.name_matches(
        "_RNvNtCs8EFNFryo1kC_12opencode_lib10project_fs24create_project_directory",
        "create_project",
    )


# ---------------------------------------------------------------------------
# extract_matches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_matches_single(impl):
    data = _fake_llvm_cov_json()
    matches = impl.extract_matches(data, "check_project_accessible")
    assert len(matches) == 1
    m = matches[0]
    assert m["lines_covered"] == 8
    assert m["lines_total"] == 10
    assert m["coverage_pct"] == pytest.approx(80.0)
    assert m["file"].endswith("project_fs.rs")
    assert "check_project_accessible" in m["function"]


@pytest.mark.unit
def test_extract_matches_none(impl):
    data = _fake_llvm_cov_json()
    assert impl.extract_matches(data, "nonexistent_command") == []


@pytest.mark.unit
def test_extract_matches_handles_zero_total(impl):
    data = _fake_llvm_cov_json()
    m = impl.extract_matches(data, "create_project")
    assert len(m) == 1
    assert m[0]["lines_total"] == 0
    assert m[0]["coverage_pct"] == 0.0


@pytest.mark.unit
def test_extract_matches_handles_empty_data(impl):
    assert impl.extract_matches({}, "anything") == []
    assert impl.extract_matches({"data": []}, "anything") == []
    assert impl.extract_matches({"data": [{}]}, "anything") == []


@pytest.mark.unit
def test_lines_from_regions_counts_covered_lines(impl):
    # Regions: [line_start, col_start, line_end, col_end, count, file_id, expanded_id, kind]
    # line 10 hit, line 11 hit, line 12-13 not hit → covered=2, total=4.
    regions = [
        [10, 1, 10, 20, 5, 0, 0, 0],
        [11, 1, 11, 20, 3, 0, 0, 0],
        [12, 1, 13, 5, 0, 0, 0, 0],
    ]
    covered, total = impl._lines_from_regions(regions)
    assert covered == 2
    assert total == 4


@pytest.mark.unit
def test_lines_from_regions_ignores_non_primary_file(impl):
    # file_id != 0 means the region is in an expanded/included file; skip it.
    regions = [
        [10, 1, 10, 20, 5, 0, 0, 0],
        [99, 1, 99, 20, 5, 1, 0, 0],  # file_id=1 → ignored
    ]
    assert impl._lines_from_regions(regions) == (1, 1)


@pytest.mark.unit
def test_lines_from_regions_skips_kind_2_regions(impl):
    # kind=2 is SkippedRegion; don't count it against totals.
    regions = [
        [10, 1, 10, 20, 5, 0, 0, 0],
        [20, 1, 20, 20, 0, 0, 0, 2],  # skipped
    ]
    assert impl._lines_from_regions(regions) == (1, 1)


@pytest.mark.unit
def test_lines_from_regions_empty(impl):
    assert impl._lines_from_regions([]) == (0, 0)


@pytest.mark.unit
def test_extract_matches_uses_regions_when_summary_missing(impl):
    data = {
        "data": [
            {
                "functions": [
                    {
                        "name": "opencode_lib::project_fs::check_project_accessible",
                        "filenames": ["/x/project_fs.rs"],
                        # No summary at all, just regions
                        "regions": [
                            [55, 1, 55, 72, 0, 0, 0, 0],
                            [56, 9, 56, 10, 7, 0, 0, 0],
                            [57, 1, 57, 10, 3, 0, 0, 0],
                        ],
                    }
                ]
            }
        ]
    }
    m = impl.extract_matches(data, "check_project_accessible")
    assert len(m) == 1
    # lines 55, 56, 57 total; 56 and 57 had count > 0 → 2/3
    assert m[0]["lines_total"] == 3
    assert m[0]["lines_covered"] == 2


# ---------------------------------------------------------------------------
# rendering (text + JSON)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_render_text_contains_expected_fields(impl):
    matches = impl.extract_matches(_fake_llvm_cov_json(), "check_project_accessible")
    out = impl.render_text("check_project_accessible", matches)
    assert "check_project_accessible" in out
    assert "project_fs.rs" in out
    assert "8/10" in out
    assert "80.0%" in out


@pytest.mark.unit
def test_render_json_is_valid_and_matches_contract(impl):
    matches = impl.extract_matches(_fake_llvm_cov_json(), "check_project_accessible")
    raw = impl.render_json("check_project_accessible", matches)
    parsed = json.loads(raw)
    assert parsed["command"] == "check_project_accessible"
    assert len(parsed["matches"]) == 1
    m = parsed["matches"][0]
    for key in ("function", "file", "lines_covered", "lines_total", "coverage_pct"):
        assert key in m


# ---------------------------------------------------------------------------
# run() end-to-end (reads a file from disk, writes to stdout)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_json_mode_emits_parseable_structure(impl, tmp_path, capsys):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    rc = impl.run("check_project_accessible", str(p), json_mode=True)
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["command"] == "check_project_accessible"
    assert len(parsed["matches"]) == 1


@pytest.mark.unit
def test_run_text_mode_emits_human_readable(impl, tmp_path, capsys):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    rc = impl.run("check_project_accessible", str(p), json_mode=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "check_project_accessible" in out
    assert "8/10" in out


@pytest.mark.unit
def test_run_returns_3_on_no_matches(impl, tmp_path, capsys):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    rc = impl.run("does_not_exist", str(p), json_mode=True)
    assert rc == 3


# ---------------------------------------------------------------------------
# Shell-script wiring: drive the bash script with COV_JSON_PATH so it skips
# the cargo llvm-cov invocation entirely. This verifies arg parsing + the
# Python handoff without needing a real Rust toolchain.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_shell_script_json_mode_via_cov_json_path(tmp_path):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    result = subprocess.run(
        [
            "bash",
            str(_SHELL_PATH),
            "check_project_accessible",
            "--json",
        ],
        env={"COV_JSON_PATH": str(p), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["command"] == "check_project_accessible"
    assert parsed["matches"][0]["lines_covered"] == 8


@pytest.mark.unit
def test_shell_script_text_mode_via_cov_json_path(tmp_path):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    result = subprocess.run(
        ["bash", str(_SHELL_PATH), "check_project_accessible"],
        env={"COV_JSON_PATH": str(p), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "check_project_accessible" in result.stdout
    assert "8/10" in result.stdout


@pytest.mark.unit
def test_shell_script_exits_2_on_missing_arg(tmp_path):
    result = subprocess.run(
        ["bash", str(_SHELL_PATH)],
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


@pytest.mark.unit
def test_shell_script_exits_2_on_unknown_flag(tmp_path):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    result = subprocess.run(
        ["bash", str(_SHELL_PATH), "check_project_accessible", "--bogus"],
        env={"COV_JSON_PATH": str(p), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unknown arg" in result.stderr


@pytest.mark.unit
def test_shell_script_exits_3_on_no_matches(tmp_path):
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_fake_llvm_cov_json()))
    result = subprocess.run(
        ["bash", str(_SHELL_PATH), "nothing_matches_this", "--json"],
        env={"COV_JSON_PATH": str(p), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3
    assert "No functions matched" in result.stderr
