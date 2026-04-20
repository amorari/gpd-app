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
