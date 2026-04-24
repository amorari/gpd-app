import json

import pytest

from gpd_tests.helpers import artifacts


@pytest.mark.unit
def test_artifact_dir_creates_nested_path(tmp_path):
    d = artifacts.artifact_dir("m1", "test_x", root=tmp_path)
    assert d.exists()
    assert d == tmp_path / "m1" / "test_x"


@pytest.mark.unit
def test_save_json_writes_pretty_json(tmp_path):
    p = artifacts.save_json(tmp_path, "window.json", {"title": "GPD"})
    assert p.exists()
    assert json.loads(p.read_text()) == {"title": "GPD"}


@pytest.mark.unit
def test_save_text_writes_string(tmp_path):
    p = artifacts.save_text(tmp_path, "log.txt", "hello\n")
    assert p.read_text() == "hello\n"


@pytest.mark.unit
def test_save_bytes_writes_binary(tmp_path):
    p = artifacts.save_bytes(tmp_path, "shot.png", b"\x89PNG\x00")
    assert p.read_bytes().startswith(b"\x89PNG")
