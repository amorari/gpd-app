import pytest


@pytest.mark.surfaces
def test_main_window_is_visible_loading_window_is_not(mcp):
    """Post-load, only the ``main`` Tauri window is a live visible surface.

    The splash at ``/loading`` is a **separate Tauri window** (see
    ``src-tauri/src/lib.rs`` around the ``loadingWindowComplete`` event and
    ``src/entry.tsx``'s path fork), not a SPA route. It is created only when
    SQLite migrations exceed ~1s and is closed once the main shell signals
    completion. By the time a test's ``mcp`` fixture is connected, loading
    is done — so we assert on window topology rather than URL transitions.
    """
    windows = mcp.list_windows()

    labels = [w.get("label") for w in windows]
    assert "main" in labels, f"expected a 'main' window among {windows!r}"

    # The loading window must not be a live visible surface. It is either
    # absent (migrations were fast / no migration needed) or present but
    # not visible. Treat missing ``visible`` as truthy to stay conservative.
    loading = [w for w in windows if w.get("label") == "loading"]
    assert not any(w.get("visible", True) for w in loading), (
        f"loading window should not be visible post-load; got {loading!r}"
    )
