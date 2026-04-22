"""Tool-use flow: assistant reads a file and quotes the sentinel it contains."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gpd_tests.helpers.llm_tolerant import assistant_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_assistant_reads_file_via_tool(http, gpd_key):
    sentinel = "psi-marker-7f3a2b"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(f"This file contains the sentinel: {sentinel}")
        path = f.name

    ses_id: str | None = None
    try:
        ses = http.create_session(directory=str(Path(path).parent))
        ses_id = ses["id"]
        http.send_message(
            ses_id,
            parts=[{
                "type": "text",
                "text": (
                    f"Read the file at {path} and report the unique sentinel "
                    "string you find inside. Do not invent one."
                ),
            }],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        msgs = http.messages(ses_id)
        assistant_msgs = [
            m for m in msgs if m.get("info", {}).get("role") == "assistant"
        ]
        assert assistant_msgs, f"no assistant message in history: {msgs!r}"
        full_text = "".join(assistant_text(m) for m in assistant_msgs)
        assert sentinel in full_text, (
            f"assistant didn't quote sentinel; full text: {full_text!r}"
        )
    finally:
        Path(path).unlink(missing_ok=True)
        if ses_id is not None:
            try:
                http.delete_session(ses_id)
            except Exception:
                pass
