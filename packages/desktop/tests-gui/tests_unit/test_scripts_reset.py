import pytest

import scripts.reset as reset


@pytest.mark.unit
def test_paths_for_tier_1():
    paths = reset.paths_for_tier(1)
    names = [p.name for p in paths]
    assert "opencode.db" in names
    assert "opencode.db-wal" in names
    assert "opencode.db-shm" in names


@pytest.mark.unit
def test_paths_for_tier_2_is_superset_of_tier_1():
    t1 = set(reset.paths_for_tier(1))
    t2 = set(reset.paths_for_tier(2))
    assert t1.issubset(t2)
    t2_names = {str(p) for p in t2}
    assert any("Application Support/inc.psi.gpd" in n for n in t2_names)
    assert any("WebKit/inc.psi.gpd" in n for n in t2_names)


@pytest.mark.unit
def test_paths_for_tier_3_includes_gpd_initialized_sentinel():
    names = {str(p) for p in reset.paths_for_tier(3)}
    assert any(n.endswith(".gpd-initialized") for n in names)


@pytest.mark.unit
def test_dry_run_does_not_delete(tmp_path, monkeypatch):
    fake_db = tmp_path / "opencode.db"
    fake_db.write_text("x")
    monkeypatch.setattr(reset, "paths_for_tier", lambda t: [fake_db])
    removed = reset.run(tier=1, dry_run=True, stop_app=False, start_app=False)
    assert removed == []
    assert fake_db.exists()


@pytest.mark.unit
def test_run_removes_existing_files(tmp_path, monkeypatch):
    fake_db = tmp_path / "opencode.db"
    fake_db.write_text("x")
    missing = tmp_path / "never_existed"
    monkeypatch.setattr(reset, "paths_for_tier", lambda t: [fake_db, missing])
    removed = reset.run(tier=1, dry_run=False, stop_app=False, start_app=False)
    assert fake_db in removed
    assert missing not in removed
    assert not fake_db.exists()
