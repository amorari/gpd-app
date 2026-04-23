"""Streaming surface tests: verify tokens visibly appear in the assistant
bubble as they arrive, not just after completion.

These are UI-level complements to the endpoint-level streaming tests —
they confirm the React render loop re-paints while bytes are still being
pushed by the sidecar.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)


_BUBBLE_SELECTOR = (
    '[data-role=\\"assistant\\"]:last-of-type, '
    '[data-component=\\"message-assistant\\"]:last-of-type, '
    '.message-assistant:last-of-type'
)

_CURSOR_SELECTOR = (
    '[data-streaming=\\"true\\"], '
    '[data-component=\\"cursor-indicator\\"], '
    '.streaming-cursor'
)

_SCROLL_CONTAINER_SELECTOR = (
    '[data-component=\\"message-list\\"], '
    '[data-component=\\"messages\\"], '
    '[data-slot=\\"messages\\"], '
    '.message-list, '
    '[role=\\"log\\"]'
)

_LONG_PROMPT = "Write a poem about octopuses with 20 verses."


@pytest.fixture
def streaming_project_dir(tmp_path_factory) -> Path:
    """Fresh per-test project dir so the session has a navigable UI route."""
    root = tmp_path_factory.mktemp(f"gpd-stream-{uuid.uuid4().hex[:8]}")
    return root.resolve()


def _navigate_to_session(mcp, directory: Path, session_id: str) -> None:
    """Open the UI on /<dir>/session/<id> so bubble DOM mounts."""
    url = route_session_in_project(encode_dir_token(str(directory)), session_id)
    Navigator(mcp).go(url, timeout_s=6.0)
    # SPA mount settle — React suspense + session fetch.
    time.sleep(0.5)


def _bubble_length(probe: DOMProbe) -> int | None:
    """Return textContent length of the latest assistant bubble, or None."""
    raw = probe.eval(
        '(() => {'
        '  const el = document.querySelector("'
        + _BUBBLE_SELECTOR
        + '");'
        '  if (!el) return -1;'
        '  return el.textContent ? el.textContent.length : 0;'
        '})()'
    )
    if raw is None:
        return None
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n


def _bubble_selector_exists(probe: DOMProbe) -> bool:
    return probe.eval_bool(
        '(() => !!document.querySelector("' + _BUBBLE_SELECTOR + '"))()'
    )


def _send_async(http, sid: str, text: str) -> tuple[threading.Thread, list]:
    """Kick off send_message in a daemon thread; poll DOM while it streams."""
    errors: list[Exception] = []

    def _send():
        try:
            http.send_message(sid, parts=[{"type": "text", "text": text}])
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    return t, errors


def _assistant_text_from_messages(msgs: list[dict]) -> str:
    out: list[str] = []
    for m in msgs:
        if m.get("info", {}).get("role") != "assistant":
            continue
        for p in m.get("parts", []):
            if p.get("type") == "text":
                out.append(p.get("text", ""))
    return "".join(out)


# ---------------------------------------------------------------------------
# 1. Incremental append
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.real_backend
def test_streaming_tokens_append_incrementally(
    http, mcp, gpd_key, streaming_project_dir
):
    """Assistant bubble textContent length grows across 4 samples in 8s."""
    probe = DOMProbe(mcp)
    ses = http.create_session(directory=str(streaming_project_dir))
    sid = ses["id"]

    try:
        _navigate_to_session(mcp, streaming_project_dir, sid)

        t, errors = _send_async(http, sid, _LONG_PROMPT)

        # Wait up to 2s for the bubble selector to appear.
        deadline = time.monotonic() + 2.0
        bubble_seen = False
        while time.monotonic() < deadline:
            try:
                if _bubble_selector_exists(probe):
                    bubble_seen = True
                    break
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            time.sleep(0.1)

        if not bubble_seen:
            pytest.xfail(
                "missing selector: none of "
                '[data-role="assistant"]:last-of-type, '
                '[data-component="message-assistant"]:last-of-type, '
                '.message-assistant:last-of-type '
                "match while streaming — product code must expose one of these "
                "on the streaming assistant message bubble"
            )

        samples: list[int] = []
        start = time.monotonic()
        while time.monotonic() - start < 8.0 and len(samples) < 4:
            try:
                n = _bubble_length(probe)
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            if n is not None and n >= 0:
                samples.append(n)
            time.sleep(0.3)

        # Let the send thread finish so the session isn't torn down mid-stream.
        t.join(timeout=30)
        if errors:
            raise errors[0]

        assert len(samples) == 4, (
            f"only captured {len(samples)} bubble length samples in 8s; "
            f"samples={samples}"
        )
        strictly_increasing = all(
            samples[i] < samples[i + 1] for i in range(len(samples) - 1)
        )
        assert strictly_increasing, (
            f"assistant bubble length did not strictly increase across "
            f"streaming samples: {samples}"
        )
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2. Cursor / streaming indicator
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.real_backend
def test_streaming_cursor_indicator_present_during_stream(
    http, mcp, gpd_key, streaming_project_dir
):
    """[data-streaming="true"] (or cursor-indicator variant) appears while
    the response is streaming and disappears once it settles."""
    probe = DOMProbe(mcp)
    ses = http.create_session(directory=str(streaming_project_dir))
    sid = ses["id"]

    try:
        _navigate_to_session(mcp, streaming_project_dir, sid)

        t, errors = _send_async(http, sid, _LONG_PROMPT)

        indicator_js = (
            '(() => !!document.querySelector("' + _CURSOR_SELECTOR + '"))()'
        )

        # Poll for indicator within 2s.
        deadline = time.monotonic() + 2.0
        present_during = False
        while time.monotonic() < deadline:
            try:
                if probe.eval_bool(indicator_js):
                    present_during = True
                    break
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            time.sleep(0.1)

        if not present_during:
            # Let the send finish before xfail so we don't leak a live stream.
            t.join(timeout=30)
            pytest.xfail(
                "missing selector: none of "
                '[data-streaming="true"], '
                '[data-component="cursor-indicator"], '
                '.streaming-cursor '
                "visible during stream — product code must expose a "
                "streaming indicator on the active assistant turn"
            )

        # Wait for server-side completion (assistant final turn in messages()).
        t.join(timeout=60)
        if errors:
            raise errors[0]

        # The server returns only when the final assistant turn exists;
        # confirm before asserting the indicator is gone.
        msgs = http.messages(sid)
        assert _assistant_text_from_messages(msgs), (
            "send_message returned but assistant has no text — "
            "cannot validate indicator-gone state"
        )

        # Give React one paint tick to clear the indicator.
        gone_deadline = time.monotonic() + 2.0
        gone = False
        while time.monotonic() < gone_deadline:
            try:
                if not probe.eval_bool(indicator_js):
                    gone = True
                    break
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            time.sleep(0.1)

        assert gone, (
            "streaming indicator still visible after assistant turn completed"
        )
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 3. Auto-scroll to bottom during streaming
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.real_backend
def test_streaming_scroll_anchors_to_bottom(
    http, mcp, gpd_key, streaming_project_dir
):
    """While streaming, the message container should stay within 50px of the
    bottom (auto-scroll). Not covered: user manually scrolling up — in that
    case the UI should stop auto-scrolling, but this test does not assert that.
    """
    probe = DOMProbe(mcp)
    ses = http.create_session(directory=str(streaming_project_dir))
    sid = ses["id"]

    try:
        _navigate_to_session(mcp, streaming_project_dir, sid)

        # Verify a scroll container selector resolves before we start the stream.
        try:
            container_present = probe.eval_bool(
                '(() => !!document.querySelector("'
                + _SCROLL_CONTAINER_SELECTOR
                + '"))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not container_present:
            pytest.xfail(
                "missing selector: none of "
                '[data-component="message-list"], '
                '[data-component="messages"], '
                '[data-slot="messages"], '
                '.message-list, '
                '[role="log"] '
                "match — product code must mark the scrolling message "
                "container with one of these"
            )

        t, errors = _send_async(http, sid, _LONG_PROMPT)

        distance_js = (
            '(() => {'
            '  const el = document.querySelector("'
            + _SCROLL_CONTAINER_SELECTOR
            + '");'
            '  if (!el) return -1;'
            '  return Math.max(0, el.scrollHeight - (el.scrollTop + el.clientHeight));'
            '})()'
        )

        # Sample scroll distance while the stream is still inflight.
        max_distance = 0
        samples = 0
        start = time.monotonic()
        while time.monotonic() - start < 6.0 and t.is_alive() and samples < 6:
            try:
                raw = probe.eval(distance_js)
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            try:
                dist = int(str(raw).strip())
            except (TypeError, ValueError):
                dist = -1
            if dist >= 0:
                samples += 1
                max_distance = max(max_distance, dist)
            time.sleep(0.4)

        t.join(timeout=30)
        if errors:
            raise errors[0]

        if samples == 0:
            pytest.skip(
                "could not sample scroll container during stream "
                "(stream completed too fast or container never mounted)"
            )

        assert max_distance <= 50, (
            f"message container drifted {max_distance}px from the bottom "
            "during streaming; auto-scroll not pinning to end"
        )
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass
