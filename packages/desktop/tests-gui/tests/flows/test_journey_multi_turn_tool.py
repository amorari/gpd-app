"""3-turn journey combining context retention and tool use.

Turn 1: plant context about a working directory.
Turn 2: ask the assistant to read a file (sentinel) — expects the read tool.
Turn 3: ask the assistant to write a file — expects the write tool and a
real on-disk artefact.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gpd_tests.helpers.llm_tolerant import assistant_text


def _tool_names(msg: dict) -> list[str]:
    """Names of tool parts in an assistant message (empty list if none)."""
    parts = msg.get("parts") or []
    return [
        str(p.get("tool", ""))
        for p in parts
        if isinstance(p, dict) and p.get("type") == "tool"
    ]


@pytest.mark.flows
@pytest.mark.real_backend
def test_journey_multi_turn_tool(http, gpd_key, tmp_path):
    sentinel = "psi-journey-9c4e1d"
    foo = tmp_path / "foo.txt"
    foo.write_text(f"The unique sentinel value is: {sentinel}\n")
    bar = tmp_path / "bar.txt"

    ses_id: str | None = None
    try:
        ses = http.create_session(directory=str(tmp_path))
        ses_id = ses["id"]

        # Turn 1: plant context about the working directory.
        http.send_message(
            ses_id,
            parts=[{
                "type": "text",
                "text": (
                    f"I'm working in the directory {tmp_path}. All subsequent "
                    "file operations should happen relative to that directory."
                ),
            }],
        )

        # Turn 2: ask to read foo.txt — must invoke the read tool.
        http.send_message(
            ses_id,
            parts=[{
                "type": "text",
                "text": (
                    "Read the file foo.txt in this directory and tell me its "
                    "contents. Quote the unique sentinel string exactly."
                ),
            }],
        )

        # Turn 3: ask to write bar.txt — must invoke the write tool.
        http.send_message(
            ses_id,
            parts=[{
                "type": "text",
                "text": (
                    "Now write the content 'done' to a file called bar.txt "
                    "in the same directory. The file's contents must be "
                    "exactly the four characters d-o-n-e with no trailing "
                    "newline or extra text."
                ),
            }],
        )

        msgs = http.messages(ses_id)
        assistant_msgs = [
            m for m in msgs if m.get("info", {}).get("role") == "assistant"
        ]
        assert len(assistant_msgs) >= 3, (
            f"expected 3 assistant turns, got {len(assistant_msgs)}: "
            f"{assistant_msgs!r}"
        )

        turn2 = assistant_msgs[1]
        turn3 = assistant_msgs[2]

        # Turn 2: read tool invoked and sentinel quoted in the reply.
        turn2_tools = _tool_names(turn2)
        assert "read" in turn2_tools, (
            f"turn 2 did not invoke the read tool; tools seen: {turn2_tools!r}"
        )
        turn2_text = assistant_text(turn2)
        assert sentinel in turn2_text, (
            f"turn 2 assistant reply did not reference the sentinel "
            f"{sentinel!r}; text: {turn2_text!r}"
        )

        # Turn 3: write tool invoked and bar.txt exists with 'done'.
        turn3_tools = _tool_names(turn3)
        assert "write" in turn3_tools, (
            f"turn 3 did not invoke the write tool; tools seen: {turn3_tools!r}"
        )
        assert bar.exists(), (
            f"turn 3 did not create bar.txt at {bar}; dir listing: "
            f"{sorted(p.name for p in tmp_path.iterdir())}"
        )
        bar_contents = bar.read_text()
        assert "done" in bar_contents, (
            f"bar.txt does not contain 'done'; got: {bar_contents!r}"
        )
    finally:
        if ses_id is not None:
            try:
                http.delete_session(ses_id)
            except Exception:
                pass
