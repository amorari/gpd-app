"""Tool-use flow: assistant reads a file and quotes the sentinel it contains."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gpd_tests.helpers.llm_tolerant import wait_for_assistant_text


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
        )
        # Poll up to 45s — the model needs to read the file (tool call
        # round-trip) and then emit text. send_message returns before the
        # assistant's final turn has streamed.
        full_text = wait_for_assistant_text(http, ses_id, timeout_s=45.0)
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
