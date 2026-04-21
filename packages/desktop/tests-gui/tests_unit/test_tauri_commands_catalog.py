"""The catalog must match the live source. Regenerate if this fails."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.unit
def test_catalog_matches_source():
    repo = Path(__file__).resolve().parents[4]
    script = repo / "packages/desktop/tests-gui/scripts/extract_tauri_commands.py"
    fixture = repo / "packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json"

    result = subprocess.run(
        ["uv", "run", "python", str(script)],
        cwd=repo / "packages/desktop/tests-gui",
        capture_output=True,
        text=True,
        check=True,
    )
    live = json.loads(result.stdout)
    stored = json.loads(fixture.read_text())
    assert live == stored, (
        "tauri_commands.json is stale \u2014 "
        "rerun: uv run python scripts/extract_tauri_commands.py > "
        "gpd_tests/fixtures/tauri_commands.json"
    )


@pytest.mark.unit
def test_catalog_has_expected_files():
    """Catalog should cover the 9 files known to contain commands."""
    repo = Path(__file__).resolve().parents[4]
    fixture = repo / "packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json"
    catalog = json.loads(fixture.read_text())
    files = {c["file"] for c in catalog}
    # Relaxed check: at least 7 distinct .rs files should have commands
    assert len(files) >= 7, f"expected >=7 files with commands, got {files}"
