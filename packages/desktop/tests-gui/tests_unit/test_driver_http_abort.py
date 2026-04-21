import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


@pytest.mark.unit
def test_abort_sends_post_to_correct_endpoint():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    c = HTTPClient(
        base_url="http://x", username="u", password="p",
        transport=httpx.MockTransport(handler),
    )
    result = c.abort("ses_abc")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/session/ses_abc/abort"
