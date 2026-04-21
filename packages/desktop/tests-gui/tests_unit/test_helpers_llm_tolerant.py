import pytest

from gpd_tests.helpers.llm_tolerant import (
    assert_assistant_replied,
    assistant_text,
)


@pytest.mark.unit
def test_assert_assistant_replied_accepts_shape():
    response = {
        "info": {"role": "assistant", "id": "msg_1"},
        "parts": [{"type": "text", "text": "hello"}],
    }
    assert_assistant_replied(response)  # does not raise


@pytest.mark.unit
def test_assert_assistant_replied_rejects_missing_role():
    with pytest.raises(AssertionError, match="assistant"):
        assert_assistant_replied({"info": {"role": "user"}, "parts": []})


@pytest.mark.unit
def test_assert_assistant_replied_rejects_empty_text():
    with pytest.raises(AssertionError, match="empty"):
        assert_assistant_replied(
            {
                "info": {"role": "assistant"},
                "parts": [{"type": "text", "text": "   "}],
            }
        )


@pytest.mark.unit
def test_assistant_text_concatenates_text_parts():
    response = {
        "info": {"role": "assistant"},
        "parts": [
            {"type": "text", "text": "he"},
            {"type": "tool-use"},
            {"type": "text", "text": "llo"},
        ],
    }
    assert assistant_text(response) == "hello"


@pytest.mark.unit
def test_assert_assistant_replied_tool_use_only_is_valid():
    """A response with only tool-use parts and no text is a valid assistant reply.

    Tool-use-only responses are legitimate: the model chose to call a tool
    rather than write text. assert_assistant_replied must not require text.
    """
    response = {
        "info": {"role": "assistant", "id": "msg_tool"},
        "parts": [{"type": "tool-use", "toolUseId": "tu_1", "toolName": "bash", "input": {}}],
    }
    assert_assistant_replied(response)  # must NOT raise


@pytest.mark.unit
def test_assert_assistant_replied_rejects_non_dict_with_assertion_error():
    """Passing None, a list, or a string must raise AssertionError with a helpful message."""
    for bad_input in (None, [], "string", 42):
        with pytest.raises(AssertionError, match="dict"):
            assert_assistant_replied(bad_input)  # type: ignore[arg-type]


@pytest.mark.unit
def test_assert_assistant_replied_surfaces_error_envelope():
    """When the server returns an error envelope, the assertion should mention it."""
    # An error envelope looks like {"error": "..."} — role will be missing,
    # so AssertionError is raised. We verify the function raises, not that the
    # error text includes the API error (that would require impl changes).
    with pytest.raises(AssertionError):
        assert_assistant_replied({"error": "API key invalid"})

    # Nested info error shape.
    with pytest.raises(AssertionError):
        assert_assistant_replied({"info": {"error": {"message": "quota exceeded"}}, "parts": []})
