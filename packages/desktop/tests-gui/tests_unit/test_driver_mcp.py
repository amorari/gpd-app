import pytest

from gpd_tests.drivers.mcp import MCPClient, MCPError


@pytest.mark.unit
def test_ping_roundtrip(fake_mcp_socket):
    def handler(req):
        assert req["command"] == "ping"
        assert req["id"]
        assert req["payload"] == {}
        return {"success": True, "data": {"value": None}, "error": None, "id": req["id"]}

    path = fake_mcp_socket(handler)
    client = MCPClient(socket_path=path)
    client.ping()


@pytest.mark.unit
def test_list_windows_returns_list(fake_mcp_socket):
    def handler(req):
        assert req["command"] == "list_windows"
        return {
            "success": True,
            "data": [{"label": "main", "title": "GPD"}],
            "error": None,
            "id": req["id"],
        }

    path = fake_mcp_socket(handler)
    client = MCPClient(socket_path=path)
    windows = client.list_windows()
    assert windows == [{"label": "main", "title": "GPD"}]


@pytest.mark.unit
def test_error_response_raises_mcperror(fake_mcp_socket):
    def handler(req):
        return {"success": False, "data": None, "error": "boom", "id": req["id"]}

    path = fake_mcp_socket(handler)
    client = MCPClient(socket_path=path)
    with pytest.raises(MCPError) as exc:
        client.ping()
    assert "boom" in str(exc.value)


@pytest.mark.unit
def test_id_is_string_and_payload_always_present(fake_mcp_socket):
    seen: list[dict] = []

    def handler(req):
        seen.append(req)
        return {"success": True, "data": None, "error": None, "id": req["id"]}

    path = fake_mcp_socket(handler)
    client = MCPClient(socket_path=path)
    client.ping()
    assert isinstance(seen[0]["id"], str)
    assert "payload" in seen[0]


@pytest.mark.unit
def test_take_screenshot_returns_data_uri(fake_mcp_socket):
    def handler(req):
        assert req["command"] == "take_screenshot"
        assert req["payload"] == {"windowLabel": "main"}
        return {
            "success": True,
            "data": {"data": "data:image/jpeg;base64,AAAA", "filePath": None},
            "error": None,
            "id": req["id"],
        }

    path = fake_mcp_socket(handler)
    c = MCPClient(socket_path=path)
    data_uri = c.take_screenshot()
    assert data_uri.startswith("data:image/jpeg;base64,")


@pytest.mark.unit
def test_navigate_webview_reload(fake_mcp_socket):
    def handler(req):
        assert req["command"] == "navigate_webview"
        assert req["payload"]["action"] == "reload"
        return {"success": True, "data": None, "error": None, "id": req["id"]}

    path = fake_mcp_socket(handler)
    MCPClient(socket_path=path).reload()


@pytest.mark.unit
def test_execute_js_returns_stringified_result(fake_mcp_socket):
    def handler(req):
        assert req["command"] == "execute_js"
        assert req["payload"] == {"code": "1+1", "windowLabel": "main"}
        return {"success": True, "data": "2", "error": None, "id": req["id"]}

    path = fake_mcp_socket(handler)
    assert MCPClient(socket_path=path).execute_js("1+1") == "2"


@pytest.mark.unit
def test_navigate_sends_navigate_action(fake_mcp_socket):
    seen = []

    def handler(req):
        seen.append(req)
        return {"success": True, "data": None, "error": None, "id": req["id"]}

    path = fake_mcp_socket(handler)
    MCPClient(socket_path=path).navigate("tauri://localhost/")
    assert seen[0]["command"] == "navigate_webview"
    assert seen[0]["payload"] == {
        "action": "navigate",
        "url": "tauri://localhost/",
        "windowLabel": "main",
    }


@pytest.mark.unit
def test_current_url_returns_url_field(fake_mcp_socket):
    def handler(req):
        return {
            "success": True,
            "data": {"url": "tauri://localhost/abc"},
            "error": None,
            "id": req["id"],
        }

    path = fake_mcp_socket(handler)
    assert MCPClient(socket_path=path).current_url() == "tauri://localhost/abc"


@pytest.mark.unit
def test_execute_js_timeout_is_distinguishable(fake_mcp_socket):
    def handler(req):
        return {
            "success": False,
            "data": None,
            "error": "Timeout waiting for JS execution",
            "id": req["id"],
        }

    path = fake_mcp_socket(handler)
    with pytest.raises(MCPError) as exc:
        MCPClient(socket_path=path).execute_js("1")
    assert "timeout" in str(exc.value).lower()
