"""E2E stress — 5 concurrent sessions, isolation + completion guarantees.

Extends test_concurrent_sessions_flow.py (2 sessions) to 5.
Each session gets a unique hexadecimal marker; after all complete we assert:
  - Every session echoed its own marker.
  - No session contains another session's marker (no context leak).
  - All 5 futures complete within 120 seconds.

A second test verifies 3 sessions each doing a 3-turn conversation in
parallel — a step up from the single-turn isolation test.
"""
from __future__ import annotations

import concurrent.futures

import pytest

from gpd_tests.helpers.llm_tolerant import assistant_text

MODEL = "claude-haiku-4-5"
PROVIDER = "gpd"
MARKERS = [
    "alpha-fa3c",
    "bravo-2e91",
    "charlie-8d04",
    "delta-6b55",
    "echo-19af",
]


def _ask_one(http, ses_id: str, marker: str) -> str:
    http.send_message(
        ses_id,
        parts=[{"type": "text", "text": f"Echo verbatim: {marker}"}],
        model_id=MODEL,
        provider_id=PROVIDER,
        agent="default",
    )
    msgs = http.messages(ses_id)
    assistant_msgs = [m for m in msgs if m.get("info", {}).get("role") == "assistant"]
    if not assistant_msgs:
        return ""
    # Use only the last assistant message to avoid false positives from earlier turns
    return assistant_text(assistant_msgs[-1])


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(300)
def test_five_concurrent_sessions_no_contamination(http, gpd_key):
    """5 simultaneous sessions each echo their own marker and contain no other marker."""
    sessions = [http.create_session() for _ in range(5)]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futs = {
                ex.submit(_ask_one, http, sessions[i]["id"], MARKERS[i]): i
                for i in range(5)
            }
            results: dict[int, str] = {}
            for fut in concurrent.futures.as_completed(futs, timeout=120):
                idx = futs[fut]
                results[idx] = fut.result()

        for i in range(5):
            assert MARKERS[i] in results[i], (
                f"session {i} ({MARKERS[i]!r}) missing from response: {results[i]!r}"
            )
            for j in range(5):
                if j != i:
                    assert MARKERS[j] not in results[i], (
                        f"cross-contamination: session {j}'s marker {MARKERS[j]!r} "
                        f"leaked into session {i}'s response: {results[i]!r}"
                    )
    finally:
        for ses in sessions:
            try:
                http.delete_session(ses["id"])
            except Exception:
                pass


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(300)
def test_three_parallel_multiturn_sessions_retain_context(http, gpd_key):
    """3 sessions, each doing a 3-turn conversation in parallel, retain their own context."""
    FACTS = ["NIGHTBIRD-7", "SOLARFOX-3", "IRONGATE-5"]
    sessions = [http.create_session() for _ in range(3)]

    def _three_turns(ses_id: str, fact: str) -> str:
        http.send_message(
            ses_id,
            parts=[{"type": "text", "text": f"My secret word is {fact}. Say 'stored'."}],
            model_id=MODEL,
            provider_id=PROVIDER,
            agent="default",
        )
        http.send_message(
            ses_id,
            parts=[{"type": "text", "text": "What is the boiling point of water in Celsius?"}],
            model_id=MODEL,
            provider_id=PROVIDER,
            agent="default",
        )
        http.send_message(
            ses_id,
            parts=[{"type": "text", "text": "What is my secret word?"}],
            model_id=MODEL,
            provider_id=PROVIDER,
            agent="default",
        )
        msgs = http.messages(ses_id)
        assistant = [m for m in msgs if m.get("info", {}).get("role") == "assistant"]
        if not assistant:
            return ""
        return "".join(
            p.get("text", "") for p in assistant[-1].get("parts", []) if p.get("type") == "text"
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = {
                ex.submit(_three_turns, sessions[i]["id"], FACTS[i]): i
                for i in range(3)
            }
            results: dict[int, str] = {}
            for fut in concurrent.futures.as_completed(futs, timeout=180):
                idx = futs[fut]
                results[idx] = fut.result()

        for i in range(3):
            assert FACTS[i].lower() in results[i].lower(), (
                f"session {i} lost its secret fact {FACTS[i]!r} in turn-3 recall. "
                f"Response: {results[i]!r}"
            )
    finally:
        for ses in sessions:
            try:
                http.delete_session(ses["id"])
            except Exception:
                pass
