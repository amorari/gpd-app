"""Phase 3 flow: default provider can be switched and is reflected in /config.

Step 1 findings (recorded here per task spec):
  - GET  /config/providers  →  {providers: [...], default: {providerID: modelID}}
    File: packages/opencode/src/server/instance/config.ts, line 63
    The "default" map is auto-computed on the read side — not a stored field.

  - PATCH /config           →  writes to <project-dir>/config.json + disposes session
    File: packages/opencode/src/server/instance/config.ts, line 38
    Validator: Config.Info (has a top-level `model` field, e.g. "anthropic/claude-3-sonnet")

  - PATCH /global/config    →  writes to the user's global opencode config file
    File: packages/opencode/src/server/instance/global.ts, line 159

  - NO dedicated POST /config/providers/default endpoint exists.

Resolution path:
  The only write paths are PATCH /config (mutates project config.json + kills live
  instance) and PATCH /global/config (mutates user's global config file). Both are
  invasive during a dev session — they clobber persistent user state and disrupt the
  running GPD. Using them without careful backup/restore in a test that "does NOT
  require real_backend" would be harmful. Therefore we take the xfail branch:

    - Part A: full shape-round-trip assertion on GET /config/providers (runs live,
      guards against shape regressions).
    - Part B: the actual provider-switch write is marked xfail with a clear message
      so CI reports it as an expected failure rather than a silent pass.

  If a dedicated write endpoint (e.g. POST /config/providers/default) is added later,
  replace the xfail block with an http.set_default_provider() call.
"""
from __future__ import annotations

import pytest


@pytest.mark.flows
def test_provider_list_shape(http):
    """GET /config/providers returns expected top-level keys and non-empty lists."""
    data = http.providers()

    # The endpoint returns an object, not a bare list.
    assert isinstance(data, dict), (
        f"expected dict from /config/providers, got {type(data).__name__}: {data!r}"
    )

    # Must have "providers" list
    assert "providers" in data, f"missing 'providers' key in response: {data.keys()}"
    providers = data["providers"]
    assert isinstance(providers, list), (
        f"'providers' field must be a list, got {type(providers).__name__}"
    )

    # Must have "default" map (may be empty if no models are loaded)
    assert "default" in data, f"missing 'default' key in response: {data.keys()}"
    default = data["default"]
    assert isinstance(default, dict), (
        f"'default' field must be a dict, got {type(default).__name__}"
    )

    # If providers are present, the first one must have at least "id" and "name".
    if providers:
        first = providers[0]
        assert "id" in first, (
            f"first provider missing 'id' field: {first!r}"
        )
        assert "name" in first, (
            f"first provider missing 'name' field: {first!r}"
        )


@pytest.mark.flows
def test_default_provider_switch_write_path_not_yet_exposed(http):
    """Provider switch round-trip: record current default, drive a change, assert.

    The write half is currently xfail — no safe dedicated write endpoint exists.
    See module docstring for full Step 1 findings and rationale.
    """
    data = http.providers()
    assert isinstance(data, dict), (
        f"expected dict from /config/providers, got {type(data).__name__}"
    )

    providers = data.get("providers", [])
    default_map = data.get("default", {})

    # Extract provider IDs from the providers list.
    ids = [p.get("id") for p in providers if p.get("id")]

    if len(ids) < 2:
        pytest.skip(
            f"need >=2 configured providers to exercise switch, got {ids}"
        )

    # Identify the current default provider: the key in the "default" map with
    # the highest-ranked model, or fall back to the first provider in the list.
    current_default = next(iter(default_map), None) or ids[0]
    new_default = next(i for i in ids if i != current_default)

    # --- Shape round-trip: assert the provider list is stable across two reads ---
    data2 = http.providers()
    ids2 = [p.get("id") for p in data2.get("providers", []) if p.get("id")]
    assert set(ids2) == set(ids), (
        f"provider list shape drifted between reads: {ids} vs {ids2}"
    )

    # --- Write path: currently xfail (see module docstring) ---
    # Uncomment and replace with http.set_default_provider(new_default) once a
    # dedicated write endpoint (e.g. POST /config/providers/default) is added.
    pytest.xfail(
        "provider write path not yet exposed via a safe dedicated endpoint; "
        f"would switch from {current_default!r} to {new_default!r} via "
        "PATCH /config {{model: '<provider>/<model>'}} but that mutates the "
        "user's persistent config and kills the live session — unsuitable for "
        "a non-destructive test. Add POST /config/providers/default and wire "
        "http.set_default_provider() to enable the round-trip assertion."
    )
