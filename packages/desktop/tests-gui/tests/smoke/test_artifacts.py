import pytest


@pytest.mark.smoke
def test_artifacts_written_on_failure(mcp):
    """Verify the on-fail artifact capture actually writes a screenshot.

    We manually invoke the capture flow and assert its output — we don't rely
    on triggering a real test failure. Window metadata comes from MCP so we
    don't steal focus from the developer.
    """
    from gpd_tests.helpers import artifacts

    d = artifacts.artifact_dir("meta", "test_artifacts_smoke")
    png = artifacts.save_bytes(d, "screenshot.jpg", mcp.take_screenshot_bytes())
    win = artifacts.save_json(d, "window.json", mcp.list_windows())

    assert png.exists() and png.stat().st_size > 100
    assert win.exists() and win.stat().st_size > 10

    for p in (png, win):
        p.unlink()
