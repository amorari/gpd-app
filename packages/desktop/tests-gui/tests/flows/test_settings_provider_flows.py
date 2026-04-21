"""Settings and provider management flow tests.

Three complementary test axes:

1. Multi-setting persistence across quit/relaunch (lifecycle)
   Extends the single-setting pattern in ``test_journey_settings_persistence.py``
   by changing TWO independently-persisted settings (theme + language) before a
   quit+relaunch cycle and asserting both survive the restart.  The model axis
   from that test is intentionally omitted here to keep this test focused on the
   dual-localStorage-channel scenario.

2. Provider enable/disable reflected in the UI (surfaces)
   Finds a currently-disabled provider, enables it via ``http.enable_provider()``,
   opens the Providers settings panel, and verifies the UI now shows that provider
   as enabled.  Then disables again and checks the reverse.  Restores original
   state in ``finally``.  No real LLM backend is needed — the test only checks
   that the HTTP state is reflected in the DOM.

3. Config PATCH error code regression (regression / flows)
   Sends a malformed body to ``PATCH /config`` and verifies the sidecar returns
   a 4xx status rather than a 500.  Regression guard for commit f36fa4626.

Persistence channels exercised
===============================

- theme    — ``localStorage["opencode-color-scheme"]``
              (packages/ui/src/theme/context.tsx, COLOR_SCHEME constant)
- language — ``localStorage["opencode.global.dat:language"]``
              (packages/app/src/utils/persist.ts, Persist.global("language"))

Lifecycle wiring
================

After quit+relaunch the sidecar PID, TCP port and basic-auth credentials all
change.  ``http.rediscover(app_state.sidecar_pid())`` rebuilds the HTTPClient in
place so subsequent HTTP calls reach the fresh process.  This mirrors the pattern
in ``test_journey_settings_persistence.py`` and
``tests/lifecycle/test_session_persistence.py``.

Markers
=======

- Test 1: ``lifecycle``, ``flows``   (excluded from the default -m filter)
- Test 2: ``surfaces``               (steals focus to open settings dialog)
- Test 3: ``flows``, ``regression``
"""
from __future__ import annotations

import copy
import json
import time

import httpx
import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


# ---------------------------------------------------------------------------
# localStorage keys — mirrored from product source
# ---------------------------------------------------------------------------

# packages/ui/src/theme/context.tsx  (COLOR_SCHEME constant)
THEME_STORAGE_KEY = "opencode-color-scheme"

# packages/app/src/utils/persist.ts  Persist.global("language") pattern
LANGUAGE_STORAGE_KEY = "opencode.global.dat:language"


# ---------------------------------------------------------------------------
# localStorage helpers (local copies — avoids cross-module import from
# test_journey_settings_persistence which lives under the same test/ dir)
# ---------------------------------------------------------------------------


def _read_ls(dom: DOMProbe, key: str) -> str | None:
    """Return raw ``localStorage[key]`` or ``None`` when absent.

    The MCP execute_js bridge may wrap JSON-string returns in an extra layer of
    quotes; we peel that layer so callers always get the bare value.
    """
    js_key = key.replace('"', '\\"')
    js = '(() => localStorage.getItem("' + js_key + '"))()'
    try:
        raw = dom.eval(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if raw is None:
        return None
    s = raw.strip()
    if s == "null":
        return None
    # Bridge sometimes wraps a JSON string return in extra quotes; peel.
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s[1:-1]
    return s


def _write_ls(dom: DOMProbe, key: str, value: str | None) -> None:
    """Write (or remove when ``None``) a localStorage key, then fire a
    ``storage`` event so reactive Solid consumers pick up the change."""
    js_key = key.replace('"', '\\"')
    if value is None:
        js = (
            '(() => { localStorage.removeItem("' + js_key + '"); '
            'window.dispatchEvent(new Event("storage")); return true; })()'
        )
    else:
        encoded = json.dumps(value)
        js = (
            '(() => { localStorage.setItem("' + js_key + '", '
            + encoded + '); '
            'window.dispatchEvent(new Event("storage")); return true; })()'
        )
    try:
        dom.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")


def _pick_other_theme(current: str | None) -> str:
    """Return the opposite theme from the known-safe ("light", "dark") pair."""
    return "dark" if current != "dark" else "light"


def _pick_other_language(current_raw: str | None) -> tuple[str, str]:
    """Return ``(locale, serialised_payload)`` distinct from ``current_raw``.

    The useLanguage() hook stores ``{ value: "<locale>", version: "language.v1" }``
    (see packages/app/src/context/language.tsx).  We mirror that shape so the
    Persist layer rehydrates cleanly after a cold restart.
    """
    current_value: str | None = None
    if current_raw:
        try:
            parsed = json.loads(current_raw)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            current_value = parsed.get("value")
        elif isinstance(parsed, str):
            current_value = parsed
    target = "fr" if current_value != "fr" else "en"
    payload = json.dumps({"value": target, "version": "language.v1"})
    return target, payload


# ---------------------------------------------------------------------------
# Settings-dialog UI helpers (adapted from test_settings_panels.py)
# ---------------------------------------------------------------------------

# Kobalte Tabs.Trigger value for the providers tab (dialog-settings.tsx)
_TAB_PROVIDERS = "providers"


def _open_settings_dialog(dom: DOMProbe, ax) -> None:
    """Open the settings dialog and wait for the General tab to appear.

    Prefers a JS-direct click on the settings gear button (no focus race).
    Falls back to Cmd+, via osascript if the button isn't found.
    """
    import subprocess

    # Dismiss any stale modal first.
    try:
        open_already = dom.eval_bool(
            '(() => !!document.querySelector('
            '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if open_already:
        import subprocess as _sp
        _sp.run(
            ["osascript", "-e",
             'tell application "System Events" to key code 53'],
            capture_output=True, check=False, timeout=5,
        )
        time.sleep(0.15)

    # Prefer direct DOM click — avoids macOS focus race.
    try:
        clicked = dom.eval_bool(
            '(() => {'
            '  const btn = document.querySelector("[aria-label=\\"Settings\\"]");'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not clicked:
        ax.activate()
        time.sleep(0.15)
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "," using command down'],
            check=True,
        )

    # Wait for the General tab to appear in the dialog.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            opened = dom.eval_bool(
                '(() => {'
                '  const tabs = Array.from(document.querySelectorAll('
                '    "[role=\\"tab\\"], [data-slot=\\"tabs-trigger\\"]"'
                '  ));'
                '  return tabs.some(t => t.textContent.trim() === "General");'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            return
        time.sleep(0.1)
    pytest.fail("settings dialog never appeared (General tab not found after 5s)")


def _close_settings_dialog(dom: DOMProbe) -> None:
    """Best-effort ESC-close of any open settings dialog."""
    import subprocess
    subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to key code 53'],
        capture_output=True, check=False, timeout=5,
    )
    time.sleep(0.2)


def _activate_tab(dom: DOMProbe, value: str) -> bool:
    """Click the settings tab whose data-value (or text) matches *value*.

    Returns True if a trigger was found and clicked.
    """
    js = (
        '(() => {'
        '  const wanted = "' + value.replace('"', '\\"') + '";'
        '  const triggers = Array.from(document.querySelectorAll('
        '    "[role=\\"tab\\"], [data-slot=\\"tabs-trigger\\"]"'
        '  ));'
        '  let hit = triggers.find('
        '    t => (t.getAttribute("data-value") || "").toLowerCase() === wanted.toLowerCase()'
        '  );'
        '  if (!hit) {'
        '    hit = triggers.find('
        '      t => t.textContent.trim().toLowerCase().includes(wanted.toLowerCase())'
        '    );'
        '  }'
        '  if (!hit) return false;'
        '  hit.click();'
        '  return true;'
        '})()'
    )
    try:
        return dom.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")


def _provider_enabled_in_ui(dom: DOMProbe, provider_id: str) -> bool:
    """Return True if *provider_id* appears in the connected-providers section.

    settings-providers.tsx renders enabled providers inside the element
    ``[data-component="connected-providers-section"]``.  The section's
    textContent contains the provider's display name (item.name), not the
    machine ID.  We search case-insensitively on the provider ID as a
    heuristic — this works for providers whose machine ID is a substring of
    their display name (e.g. "anthropic" ⊆ "Anthropic Claude").

    The former "Strategy A" that searched for ``[data-provider-id]`` attributes
    was removed: that attribute does not exist in the actual settings-providers
    DOM.
    """
    pid_lower = provider_id.lower().replace('"', '\\"')
    js = (
        '(() => {'
        '  const section = document.querySelector('
        '    "[data-component=\\"connected-providers-section\\"]"'
        '  );'
        '  if (!section) return false;'
        '  return section.textContent.toLowerCase().includes("' + pid_lower + '");'
        '})()'
    )
    try:
        return dom.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")


# ---------------------------------------------------------------------------
# Test 1 — multi-setting persistence across quit/relaunch
# ---------------------------------------------------------------------------


@pytest.mark.lifecycle
@pytest.mark.flows
def test_multi_setting_persistence_theme_and_language(http, mcp, app_state):
    """Change theme + language simultaneously, quit/relaunch, verify both persist.

    Each setting lives in a different localStorage key (two independent
    persistence channels), so this is a mini cross-check that BOTH channels
    survive a cold sidecar restart.  The model channel (Config.Info.model via
    PATCH /config) is covered separately in
    ``test_journey_settings_persistence.py``; this test deliberately keeps the
    HTTP layer out of scope to focus exclusively on the dual-localStorage path.

    Lifecycle wiring follows the pattern in test_journey_settings_persistence:
    after quit+relaunch, http.rediscover() re-points the client at the fresh
    sidecar. We MCP-ping first to ensure the webview is responsive.

    Original values are restored in ``finally`` — the developer's GPD is left
    exactly as it was before the test.
    """
    dom = DOMProbe(mcp)

    # --- 1. Snapshot originals -------------------------------------------

    original_theme_raw = _read_ls(dom, THEME_STORAGE_KEY)
    original_language_raw = _read_ls(dom, LANGUAGE_STORAGE_KEY)

    # Guard: only toggle between known-safe theme values; custom/system/auto
    # themes are not touched (same policy as test_theme_switch.py).
    if original_theme_raw not in (None, "dark", "light"):
        pytest.skip(
            f"{THEME_STORAGE_KEY!r} is {original_theme_raw!r} "
            "(custom/system/auto); skipping to avoid clobbering"
        )

    # --- 2. Pick targets and apply them ----------------------------------

    target_theme = _pick_other_theme(original_theme_raw)
    target_language, target_language_payload = _pick_other_language(
        original_language_raw
    )

    try:
        _write_ls(dom, THEME_STORAGE_KEY, target_theme)
        _write_ls(dom, LANGUAGE_STORAGE_KEY, target_language_payload)

        # --- 3. Verify in-process (pre-restart) --------------------------

        observed_theme_pre = _read_ls(dom, THEME_STORAGE_KEY)
        observed_language_pre = _read_ls(dom, LANGUAGE_STORAGE_KEY)

        assert observed_theme_pre == target_theme, (
            f"theme set but not observed in-process: "
            f"got {observed_theme_pre!r}, expected {target_theme!r}"
        )
        assert observed_language_pre is not None and target_language in observed_language_pre, (
            f"language set but not observed in-process: "
            f"got {observed_language_pre!r}, expected contains {target_language!r}"
        )

        # --- 4. Destructive: quit + relaunch -----------------------------

        app_state.quit()
        app_state.wait_quit(timeout_s=15)
        app_state.launch()
        app_state.wait_launched()

        # --- 5. F9 rediscover — new PID, port, creds --------------------

        new_pid = app_state.sidecar_pid()
        if new_pid is None:
            pytest.fail(
                "sidecar PID not found after relaunch — rediscover impossible"
            )
        http.rediscover(new_pid)

        # --- 6. Re-read via DOM probe ------------------------------------

        post_theme = _read_ls(dom, THEME_STORAGE_KEY)
        post_language = _read_ls(dom, LANGUAGE_STORAGE_KEY)

        # --- 7. Assert both persisted ------------------------------------

        assert post_theme == target_theme, (
            f"theme did not persist across quit/relaunch: "
            f"got {post_theme!r}, expected {target_theme!r}"
        )
        assert post_language is not None and target_language in post_language, (
            f"language did not persist across quit/relaunch: "
            f"got {post_language!r}, expected contains {target_language!r}"
        )

    finally:
        # --- 8. Restore originals (each independently) ------------------
        try:
            _write_ls(dom, THEME_STORAGE_KEY, original_theme_raw)
        except Exception:
            pass
        try:
            _write_ls(dom, LANGUAGE_STORAGE_KEY, original_language_raw)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 2 — provider enable/disable reflected in UI
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_provider_enable_disable_reflected_in_ui(http, mcp, ax):
    """Enable a disabled provider via HTTP, verify the UI reflects enabled state.

    Flow:
      1. Find a provider that is currently listed in ``disabled_providers``.
         If none is disabled, skip (no safe target to toggle without side-effects).
      2. Enable it via ``http.enable_provider()``.
      3. Open settings → Providers tab.
      4. Assert the provider shows as enabled in the DOM.
      5. Disable via ``http.disable_provider()``.
      6. Assert the DOM reflects disabled state.
      7. Re-enable to restore original state.
      8. Close dialog.

    No real LLM backend needed — this test only verifies that the UI reads
    provider state from the sidecar correctly.  Marked ``surfaces`` because it
    opens the settings dialog (steals_focus).
    """
    dom = DOMProbe(mcp)
    original_cfg = http.get_config()
    snapshot = copy.deepcopy(original_cfg)

    # --- 1. Find a disabled provider to toggle ---------------------------

    data = http.list_providers_full()
    all_ids = [pid for p in data.get("all", []) if (pid := p.get("id"))]
    if not all_ids:
        pytest.skip("no providers reported by /provider — cannot exercise toggle")

    originally_disabled = set(snapshot.get("disabled_providers") or [])
    if not originally_disabled:
        pytest.skip(
            "no providers are currently disabled; "
            "cannot test enable-from-disabled without a disabled target. "
            "Manually disable one provider in settings and re-run."
        )

    # Pick the first currently-disabled provider that is in /provider's all list.
    target = next(
        (pid for pid in all_ids if pid in originally_disabled), None
    )
    if target is None:
        pytest.skip(
            "disabled_providers lists IDs not present in /provider 'all'; "
            "cannot exercise the toggle safely"
        )

    dialog_opened = False
    try:
        # --- 2. Enable via HTTP ------------------------------------------

        new_cfg = http.enable_provider(target)
        assert target not in (new_cfg.get("disabled_providers") or []), (
            f"enable_provider({target!r}) did not remove from disabled_providers: "
            f"{new_cfg.get('disabled_providers')!r}"
        )

        # --- 3. Open settings → Providers tab ----------------------------

        Navigator(mcp).go(route_home(), timeout_s=5.0)
        _open_settings_dialog(dom, ax)
        dialog_opened = True

        activated = _activate_tab(dom, _TAB_PROVIDERS)
        if not activated:
            pytest.skip("providers tab trigger not found in settings dialog")

        # Give Kobalte time to mount the panel content.
        time.sleep(0.3)

        # --- 4. Assert enabled in UI -------------------------------------

        enabled_in_ui = _provider_enabled_in_ui(dom, target)
        assert enabled_in_ui, (
            f"provider {target!r} was enabled via HTTP but does not appear "
            "enabled in the settings Providers tab UI"
        )

        # --- 5. Disable via HTTP -----------------------------------------

        disabled_cfg = http.disable_provider(target)
        assert target in (disabled_cfg.get("disabled_providers") or []), (
            f"disable_provider({target!r}) did not add to disabled_providers: "
            f"{disabled_cfg.get('disabled_providers')!r}"
        )

        # Allow the UI to react to the config change (reactive store propagation).
        time.sleep(0.3)

        # --- 6. Assert disabled in UI ------------------------------------

        # Re-activate tab to force panel refresh, then check.
        _activate_tab(dom, _TAB_PROVIDERS)
        time.sleep(0.25)

        still_enabled_in_ui = _provider_enabled_in_ui(dom, target)
        assert not still_enabled_in_ui, (
            f"provider {target!r} was disabled via HTTP but still appears "
            "enabled in the settings Providers tab UI"
        )

    finally:
        # --- 7. Close dialog and restore original state ------------------
        if dialog_opened:
            try:
                _close_settings_dialog(dom)
            except Exception:
                pass
        try:
            http.patch_config(snapshot)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 3 — Config PATCH error code regression (fix f36fa4626)
# ---------------------------------------------------------------------------


@pytest.mark.flows
@pytest.mark.regression
def test_patch_config_malformed_body_returns_4xx_not_500(http):
    """PATCH /config with a malformed body must return 400 or 422, never 500.

    Regression guard for commit f36fa4626 which fixed the server returning a
    500 Internal Server Error when the request body failed Zod validation.
    The correct behaviour is to return a 4xx (typically 400 Bad Request or
    422 Unprocessable Entity) so callers can distinguish a client error from
    a server bug.

    Two malformed shapes are tested:
      - A JSON array (not an object at all) — caught by Zod's ``.object()``
        validator before any field-level check fires.
      - A string scalar — similarly caught at the envelope level.

    Neither mutates the config: the server must reject both without writing
    anything. A defensive GET-then-restore is still done in ``finally`` in
    case an exotic sidecar version silently accepts one of these shapes.
    """
    original_cfg = http.get_config()
    snapshot = copy.deepcopy(original_cfg)

    bad_payloads: list[tuple[str, object]] = [
        ("JSON array", ["not", "a", "config", "object"]),
        ("JSON string scalar", "this is not a config object"),
    ]

    try:
        for description, bad_payload in bad_payloads:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                # Bypass the type-checked patch_config() wrapper so we can
                # send an intentionally wrong shape. _patch() is the thin
                # httpx wrapper that calls raise_for_status().
                http._patch("/config", json=bad_payload)  # type: ignore[arg-type]

            status = exc_info.value.response.status_code
            assert 400 <= status < 500, (
                f"PATCH /config with {description} returned HTTP {status}; "
                f"expected 4xx (not 500). "
                f"This is a regression of fix f36fa4626 — the server must "
                f"validate the request body and return a client-error code."
            )
    finally:
        # Defensive restore: if any bad PATCH somehow landed (exotic sidecar
        # that doesn't validate), put the original config back.
        try:
            http.patch_config(snapshot)
        except Exception:
            pass
