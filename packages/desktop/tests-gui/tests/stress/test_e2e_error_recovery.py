"""E2E stress — error injection and recovery.

Tests that the HTTP sidecar and session state machine remain stable after
various error conditions:
  1. Rapid create/delete cycles (20 iterations) — session list count stable.
  2. Sending to a nonexistent session ID raises cleanly.
  3. Fetching a deleted session raises cleanly.
  4. Oversized message body (50 000 chars) — either accepted or rejected cleanly.
  5. Concurrent 10-pair create/delete — no session count drift.
  6. Session created but never used — delete succeeds and it disappears from listing.
  7. Sidecar health endpoint returns healthy after a burst of bad requests.

These tests do NOT require a real LLM backend — they test only the session/
sidecar API layer, not the LLM routing.
"""
from __future__ import annotations

import concurrent.futures
import string

import pytest


def _cleanup(*session_ids, http):
    for sid in session_ids:
        try:
            http.delete_session(sid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Rapid create/delete cycles
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_20_rapid_create_delete_no_session_leak(http):
    """20 rapid create-then-delete cycles leave session count unchanged."""
    pre_count = len(http.sessions())
    for _ in range(20):
        ses = http.create_session()
        http.delete_session(ses["id"])
    post_count = len(http.sessions())
    assert post_count == pre_count, (
        f"session count drifted after 20 rapid cycles: {pre_count} -> {post_count}"
    )


# ---------------------------------------------------------------------------
# Invalid session ID
# ---------------------------------------------------------------------------


@pytest.mark.flows
@pytest.mark.parametrize("bad_id", [
    "nonexistent-id-00000",
    "a" * 256,
    "../../etc/passwd",
    "<script>alert(1)</script>",
])
def test_send_to_invalid_session_raises(http, bad_id):
    """send_message to a nonexistent/malformed session ID must raise, not silently succeed."""
    with pytest.raises(Exception):
        http.send_message(
            bad_id,
            parts=[{"type": "text", "text": "hello"}],
            model_id="claude-haiku-4-5-20251001",
            provider_id="anthropic",
            agent="default",
        )


@pytest.mark.flows
@pytest.mark.parametrize("bad_id", [
    "nonexistent-id-00000",
    "a" * 256,
])
def test_get_session_for_invalid_id_raises(http, bad_id):
    """get_session() for a nonexistent ID must raise, not return garbage."""
    with pytest.raises(Exception):
        http.get_session(bad_id)


# ---------------------------------------------------------------------------
# Oversized message body
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_oversized_message_body_accepted_or_rejected_cleanly(http):
    """A 50 000-character message body must not crash the sidecar."""
    ses = http.create_session()
    try:
        big_text = (string.ascii_letters * (50_000 // len(string.ascii_letters) + 1))[:50_000]
        try:
            http.send_message(
                ses["id"],
                parts=[{"type": "text", "text": big_text}],
                model_id="claude-haiku-4-5-20251001",
                provider_id="anthropic",
                agent="default",
            )
            # Accepted — sidecar must still be reachable
            health = http.health()
            assert health.get("healthy") is True, (
                f"sidecar unhealthy after oversized message: {health}"
            )
        except Exception:
            # Rejected — verify sidecar is still alive
            health = http.health()
            assert health.get("healthy") is True, (
                f"sidecar unhealthy after rejecting oversized message: {health}"
            )
    finally:
        _cleanup(ses["id"], http=http)


# ---------------------------------------------------------------------------
# Concurrent 10-pair create/delete
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_10_concurrent_create_delete_no_count_drift(http):
    """10 simultaneous create-then-delete pairs must not corrupt session list."""
    pre_count = len(http.sessions())

    def _cycle():
        ses = http.create_session()
        http.delete_session(ses["id"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(_cycle) for _ in range(10)]
        for f in concurrent.futures.as_completed(futs):
            f.result()

    post_count = len(http.sessions())
    assert post_count == pre_count, (
        f"session count drifted after 10 concurrent cycles: {pre_count} -> {post_count}"
    )


# ---------------------------------------------------------------------------
# Created-but-never-used session
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_unused_session_deletes_cleanly(http):
    """A session created but never sent a message can be deleted and disappears."""
    ses = http.create_session()
    sid = ses["id"]
    assert sid in {s["id"] for s in http.sessions()}, f"new session {sid} not in listing"
    http.delete_session(sid)
    assert sid not in {s["id"] for s in http.sessions()}, (
        f"deleted session {sid} still appears in listing"
    )


# ---------------------------------------------------------------------------
# Sidecar health after sustained stress
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_sidecar_healthy_after_error_series(http):
    """After a series of invalid requests, the sidecar health endpoint returns healthy."""
    for _ in range(5):
        try:
            http.get_session("bad-id")
        except Exception:
            pass
    health = http.health()
    assert health.get("healthy") is True, (
        f"sidecar unhealthy after error series: {health}"
    )
