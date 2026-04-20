"""Phase 3 flow: create a session, send a prompt, assert the shape of the reply."""
from __future__ import annotations

import pytest

from gpd_tests.helpers.llm_tolerant import assert_assistant_replied


@pytest.mark.flows
@pytest.mark.real_backend
def test_new_session_send_prompt_assistant_replies(
    http, scratch_project_dir, anthropic_key
):
    # 1. Create session in the scratch dir.
    session = http.create_session(directory=str(scratch_project_dir))
    assert "id" in session, f"create_session returned {session!r}"
    sid = session["id"]

    # 2. Send a prompt. 60 s ceiling (pytest default --timeout=60).
    response = http.send_message(
        sid,
        parts=[{"type": "text", "text": "Say hi."}],
    )

    # 3. Shape-only assertions — LLM content is not asserted.
    assert_assistant_replied(response)

    # 4. Session appears in list scoped to our dir.
    listed = http.sessions()
    found = [s for s in listed if s.get("id") == sid]
    assert found, f"created session {sid} not in /session list"

    # 5. Message history has at least one user + one assistant entry.
    msgs = http.messages(sid)
    roles = [m.get("info", {}).get("role") or m.get("role") for m in msgs]
    assert "user" in roles, f"no user message in history: {roles}"
    assert "assistant" in roles, f"no assistant message in history: {roles}"
