"""Two concurrent sessions must not cross-contaminate context."""
from __future__ import annotations

import concurrent.futures

import pytest

from gpd_tests.helpers.llm_tolerant import assistant_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_two_sessions_do_not_cross_contaminate(http, anthropic_key):
    ses_a = http.create_session()
    ses_b = http.create_session()

    def _ask(ses_id: str, marker: str) -> str:
        http.send_message(
            ses_id,
            parts=[{
                "type": "text",
                "text": f"Echo this unique marker back to me verbatim: {marker}",
            }],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        msgs = http.messages(ses_id)
        assistant_msgs = [
            m for m in msgs if m.get("info", {}).get("role") == "assistant"
        ]
        return "".join(assistant_text(m) for m in assistant_msgs)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(_ask, ses_a["id"], "alpha-7f3a")
            fb = ex.submit(_ask, ses_b["id"], "bravo-2c4e")
            ta = fa.result(timeout=90)
            tb = fb.result(timeout=90)
        assert "alpha-7f3a" in ta, (
            f"session A didn't echo its marker: {ta!r}"
        )
        assert "bravo-2c4e" in tb, (
            f"session B didn't echo its marker: {tb!r}"
        )
        assert "alpha-7f3a" not in tb, (
            "cross-contamination: A's marker leaked into B"
        )
        assert "bravo-2c4e" not in ta, (
            "cross-contamination: B's marker leaked into A"
        )
    finally:
        for sid in (ses_a["id"], ses_b["id"]):
            try:
                http.delete_session(sid)
            except Exception:
                pass
