"""Shape-only tests for HTTPClient /config + /provider helpers.

TDD-first coverage for Task G3.2: verify the driver methods hit the right
routes with the right methods, parse the real server payload shapes, and
handle 4xx validation failures loudly. No live GPD required.
"""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _client(**kwargs) -> HTTPClient:
    return HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_config_returns_config_info_shape():
    payload = {
        "$schema": "https://opencode.ai/config.json",
        "model": "anthropic/claude-4-7",
        "disabled_providers": [],
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    c = _client(transport=httpx.MockTransport(handler))
    data = c.get_config()
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/config"
    assert data == payload


@pytest.mark.unit
def test_get_config_401_raises():
    c = _client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(401, json={"error": "unauthorized"})
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.get_config()
    assert exc_info.value.response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_patch_config_sends_patch_body_and_returns_info():
    seen: list[httpx.Request] = []
    patch = {"model": "anthropic/claude-4-7", "disabled_providers": ["foo"]}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=patch)

    c = _client(transport=httpx.MockTransport(handler))
    result = c.patch_config(patch)
    assert seen[0].method == "PATCH"
    assert seen[0].url.path == "/config"
    body = json.loads(seen[0].content)
    assert body == patch
    assert result == patch


@pytest.mark.unit
def test_patch_config_400_raises_http_status_error():
    """Invalid-shape PATCH must raise; silent accept would hide config corruption."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "zod validation failed"})

    c = _client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.patch_config({"not_a_real_field": 42})
    assert exc_info.value.response.status_code == 400


# ---------------------------------------------------------------------------
# GET /provider  (deeper than /config/providers)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_providers_full_returns_all_default_connected_shape():
    """GET /provider returns { all, default, connected } — verify the trio."""
    payload = {
        "all": [
            {
                "id": "anthropic",
                "name": "Anthropic",
                "models": {"claude-4-7": {"id": "claude-4-7", "name": "Claude 4.7"}},
                "env": [],
                "options": {},
                "source": "embedded",
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "models": {"gpt-5": {"id": "gpt-5", "name": "GPT-5"}},
                "env": [],
                "options": {},
                "source": "embedded",
            },
        ],
        "default": {"anthropic": "claude-4-7", "openai": "gpt-5"},
        "connected": ["anthropic"],
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    c = _client(transport=httpx.MockTransport(handler))
    data = c.list_providers_full()
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/provider"
    assert isinstance(data, dict)
    assert isinstance(data["all"], list)
    assert isinstance(data["default"], dict)
    assert isinstance(data["connected"], list)
    # Per-provider shape
    for p in data["all"]:
        assert "id" in p
        assert "name" in p
        assert "models" in p
        assert isinstance(p["models"], dict)
    assert data["connected"] == ["anthropic"]


@pytest.mark.unit
def test_list_providers_full_distinct_from_config_providers_endpoint():
    """Regression: /provider is NOT /config/providers; ensure the path is right.

    /config/providers returns `{providers, default}` (no `connected`, no `all`).
    """
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"all": [], "default": {}, "connected": []})

    c = _client(transport=httpx.MockTransport(handler))
    c.list_providers_full()
    assert seen[0].url.path == "/provider"
    assert seen[0].url.path != "/config/providers"


# ---------------------------------------------------------------------------
# provider_models(id)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_provider_models_returns_models_dict_for_given_id():
    payload = {
        "all": [
            {
                "id": "anthropic",
                "name": "Anthropic",
                "models": {
                    "claude-4-7": {"id": "claude-4-7"},
                    "claude-3-sonnet": {"id": "claude-3-sonnet"},
                },
            }
        ],
        "default": {"anthropic": "claude-4-7"},
        "connected": ["anthropic"],
    }

    c = _client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    )
    models = c.provider_models("anthropic")
    assert set(models.keys()) == {"claude-4-7", "claude-3-sonnet"}
    assert models["claude-4-7"]["id"] == "claude-4-7"


@pytest.mark.unit
def test_provider_models_unknown_id_raises_key_error():
    payload = {"all": [{"id": "anthropic", "models": {}}], "default": {}, "connected": []}
    c = _client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    )
    with pytest.raises(KeyError):
        c.provider_models("does-not-exist")


# ---------------------------------------------------------------------------
# enable_provider / disable_provider
# ---------------------------------------------------------------------------


def _mux_handler(config_store: dict) -> httpx.MockTransport:
    """Simulate GET/PATCH /config round-trip against an in-memory store."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/config":
            return httpx.Response(200, json=config_store)
        if request.method == "PATCH" and request.url.path == "/config":
            new_cfg = json.loads(request.content)
            config_store.clear()
            config_store.update(new_cfg)
            return httpx.Response(200, json=config_store)
        return httpx.Response(404, json={"error": "no route"})

    return httpx.MockTransport(handler)


@pytest.mark.unit
def test_disable_provider_adds_to_disabled_providers_list():
    store = {"model": "anthropic/claude-4-7", "disabled_providers": []}
    c = _client(transport=_mux_handler(store))
    new_cfg = c.disable_provider("openai")
    assert "openai" in new_cfg["disabled_providers"]
    assert store["disabled_providers"] == ["openai"]


@pytest.mark.unit
def test_disable_provider_is_idempotent():
    """Calling disable twice must not duplicate the id in disabled_providers."""
    store = {"disabled_providers": ["openai"]}
    c = _client(transport=_mux_handler(store))
    c.disable_provider("openai")
    assert store["disabled_providers"] == ["openai"], (
        f"duplicate entry introduced: {store}"
    )


@pytest.mark.unit
def test_enable_provider_removes_from_disabled_providers_list():
    store = {"model": "anthropic/claude-4-7", "disabled_providers": ["openai", "google"]}
    c = _client(transport=_mux_handler(store))
    new_cfg = c.enable_provider("openai")
    assert "openai" not in new_cfg["disabled_providers"]
    assert new_cfg["disabled_providers"] == ["google"]


@pytest.mark.unit
def test_enable_provider_appends_to_enabled_providers_when_allowlist_active():
    """When enabled_providers is an allowlist, enable() must also add the id there.

    Otherwise removing from disabled_providers alone has no effect.
    """
    store = {"enabled_providers": ["anthropic"], "disabled_providers": []}
    c = _client(transport=_mux_handler(store))
    c.enable_provider("openai")
    assert set(store["enabled_providers"]) == {"anthropic", "openai"}


@pytest.mark.unit
def test_disable_provider_removes_from_enabled_allowlist():
    """When enabled_providers is an allowlist, disable() must also strip the id."""
    store = {"enabled_providers": ["anthropic", "openai"], "disabled_providers": []}
    c = _client(transport=_mux_handler(store))
    c.disable_provider("openai")
    assert "openai" in store["disabled_providers"]
    assert "openai" not in store["enabled_providers"]


@pytest.mark.unit
def test_enable_provider_propagates_400_on_invalid_config():
    """If the server rejects the PATCH, enable_provider must not swallow."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/config":
            return httpx.Response(200, json={"disabled_providers": ["openai"]})
        if request.method == "PATCH":
            return httpx.Response(400, json={"error": "zod validation failed"})
        return httpx.Response(404)

    c = _client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.enable_provider("openai")
    assert exc_info.value.response.status_code == 400
