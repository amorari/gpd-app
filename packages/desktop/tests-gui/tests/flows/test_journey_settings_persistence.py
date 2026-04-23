"""Task G6.5: multi-setting persistence across a quit/relaunch cycle.

End-to-end user journey: change theme, default provider model, and
language, then quit + relaunch GPD and verify all three values survive
the restart. This extends the single-axis coverage of
``tests/flows/test_theme_switch.py`` (theme only, no restart) by binding
all three settings into one lifecycle test.

Storage layers exercised
========================

Each setting lives in a different persistence channel, so this test is
also a mini cross-check that all three channels are re-hydrated after a
cold sidecar restart:

  - theme       — ``localStorage["opencode-color-scheme"]``
                  (see ``packages/app/public/oc-theme-preload.js``;
                  key defined in ``packages/ui/src/theme/context.tsx``)
  - model       — ``Config.Info.model`` via ``http.patch_config``
                  (see ``packages/opencode/src/config/config.ts:466``)
  - language    — ``localStorage["opencode.global.dat:language"]``
                  per G5.8 finding (``test_settings_panels.py`` docstring)
                  — the frontend ``useLanguage()`` hook persists via
                  ``Persist.global("language")`` rather than routing
                  through the sidecar config.

Lifecycle wiring
================

After ``app_state.quit()`` + ``app_state.launch()`` the opencode-cli
sidecar reappears on a new TCP port with fresh basic-auth creds, so the
``HTTPClient`` from the fixture is pinned to a dead process. Per F9, we
call ``http.rediscover(app_state.sidecar_pid())`` before re-reading
``/config`` — this mirrors the pattern already used in
``tests/lifecycle/test_session_persistence.py`` and
``tests/lifecycle/test_session_list_persistence.py``.

Markers
=======

Marked ``lifecycle + flows``. ``lifecycle`` is not in the default pytest
selection (see ``pytest.ini:addopts``), so this test only runs on
explicit ``-m lifecycle`` invocations — avoiding an incidental GPD
quit+relaunch on developer machines during ordinary test runs.
"""
from __future__ import annotations

import copy
import json
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


# --- localStorage keys (mirrored from product code) -----------------------

# ``packages/ui/src/theme/context.tsx`` COLOR_SCHEME constant.
THEME_STORAGE_KEY = "opencode-color-scheme"

# ``packages/app/src/utils/persist.ts`` pattern: "opencode.global.dat:<key>"
# for Persist.global(...) entries. ``useLanguage()`` uses "language".
LANGUAGE_STORAGE_KEY = "opencode.global.dat:language"


# --- localStorage helpers -------------------------------------------------
#
# Kept inline (not imported from test_settings_panels) because that module
# is under tests/surfaces/ and pulls in Navigator + settings-dialog open
# flow that this lifecycle test doesn't need. The DOM probe shape is small
# enough that local duplication is cheaper than a shared helpers module.


def _read_ls(dom: DOMProbe, key: str) -> str | None:
    """Return raw ``localStorage[key]`` or ``None`` if absent.

    MCP ``execute_js`` returns values as strings; we normalize JS ``null``
    to Python ``None`` so callers can compare against a sentinel cleanly.
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
    # Bridge occasionally wraps JSON string returns in extra quotes; peel.
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s[1:-1]
    return s


def _write_ls(dom: DOMProbe, key: str, raw_value: str | None) -> None:
    """Write (or delete when ``None``) a localStorage entry.

    Also fires a ``storage`` event so reactive consumers (ThemeProvider,
    LanguageProvider) pick the change up without a full reload, matching
    what ``test_theme_switch.py`` does.
    """
    js_key = key.replace('"', '\\"')
    # intentional: testing synthetic event path — the `storage` event is the
    # browser's cross-context localStorage sync signal; ThemeProvider and
    # LanguageProvider subscribe to it to rehydrate state without reload. It
    # has no OS-level equivalent (there is no keystroke or click that produces
    # a StorageEvent on the current window), so firing it via dispatchEvent is
    # the only way to exercise the reactive pathway.
    if raw_value is None:
        js = (
            '(() => { localStorage.removeItem("' + js_key + '"); '
            'window.dispatchEvent(new Event("storage")); return true; })()'
        )
    else:
        encoded = json.dumps(raw_value)
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
    """Return a theme value distinct from ``current``, drawn from the
    known-safe pair ("light", "dark")."""
    if current == "light":
        return "dark"
    return "light"


def _pick_other_language(current_raw: str | None) -> tuple[str, str]:
    """Return ``(target_locale, raw_payload)`` that differs from ``current_raw``.

    ``useLanguage()`` writes a JSON-encoded object with shape
    ``{value, version: "language.v1"}`` (see
    ``packages/app/src/context/language.tsx`` / ``utils/persist.ts``). We
    mirror that shape so the Persist layer rehydrates cleanly on reload.
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


def _pick_other_model(
    current_model: str | None, providers_full: dict
) -> str | None:
    """Return a ``provider/model`` id distinct from ``current_model``.

    Walks ``list_providers_full()['all']`` for the first (provider, model)
    pair whose id differs from the current setting. Returns ``None`` if
    the sidecar reports no models at all (unlikely on any real run, but
    we skip cleanly in that case).
    """
    for p in providers_full.get("all", []) or []:
        provider_id = p.get("id")
        models = p.get("models") or {}
        for model_id in models.keys():
            candidate = f"{provider_id}/{model_id}"
            if candidate != current_model:
                return candidate
    return None


# --- Test -----------------------------------------------------------------


@pytest.mark.lifecycle
@pytest.mark.flows
def test_multi_setting_persistence_across_quit_relaunch(http, mcp, app_state):
    """Change theme, model, language → quit/relaunch → all three persist.

    One destructive quit+launch cycle exercises three independent
    persistence channels. ``finally`` restores every value we touched
    (including on assertion failure) so the suite leaves the developer's
    GPD with the exact pre-test configuration.
    """
    dom = DOMProbe(mcp)

    # --- 1. Snapshot originals ------------------------------------------

    original_theme_raw = _read_ls(dom, THEME_STORAGE_KEY)
    original_language_raw = _read_ls(dom, LANGUAGE_STORAGE_KEY)
    original_config = http.get_config()
    original_config_snapshot = copy.deepcopy(original_config)
    original_model = original_config.get("model")

    # Only toggle theme between known-safe values; if the dev has a custom
    # theme set we skip rather than risk clobbering it (same policy as
    # test_theme_switch.py).
    if original_theme_raw not in (None, "dark", "light"):
        pytest.skip(
            f"{THEME_STORAGE_KEY} is {original_theme_raw!r} "
            "(custom/system/auto); skipping to avoid clobbering it"
        )

    # --- 2. Pick distinct targets and apply them ------------------------

    providers_full = http.list_providers_full()
    target_model = _pick_other_model(original_model, providers_full)
    if target_model is None:
        pytest.skip("no provider models reported by /provider; cannot pick target")

    target_theme = _pick_other_theme(original_theme_raw)
    target_language, target_language_payload = _pick_other_language(
        original_language_raw
    )

    # Flag tracks whether PATCH /config landed; only then does the finally
    # need to restore /config. Separate from the localStorage flags because
    # those are idempotent — writing back the original value is cheap.
    config_patched = False

    try:
        # Apply: localStorage writes first (synchronous), then PATCH
        # /config (round-trip). Order doesn't matter for the restart
        # assertion, but doing LS first means a transient PATCH failure
        # still leaves us with recoverable state.
        _write_ls(dom, THEME_STORAGE_KEY, target_theme)
        _write_ls(dom, LANGUAGE_STORAGE_KEY, target_language_payload)

        new_config = copy.deepcopy(original_config)
        new_config["model"] = target_model
        http.patch_config(new_config)
        config_patched = True

        # --- 3. Verify in-process reads see the new values --------------

        observed_theme_pre = _read_ls(dom, THEME_STORAGE_KEY)
        observed_language_pre = _read_ls(dom, LANGUAGE_STORAGE_KEY)
        observed_config_pre = http.get_config()

        assert observed_theme_pre == target_theme, (
            f"theme set but not observed in-process: "
            f"got {observed_theme_pre!r}, expected {target_theme!r}"
        )
        assert observed_language_pre is not None and target_language in observed_language_pre, (
            f"language set but not observed in-process: "
            f"got {observed_language_pre!r}, expected contains {target_language!r}"
        )
        assert observed_config_pre.get("model") == target_model, (
            f"model set but not observed in-process: "
            f"got {observed_config_pre.get('model')!r}, expected {target_model!r}"
        )

        # --- 4. Destructive: quit + relaunch ----------------------------
        #
        # WebKit's localStorage.setItem() flushes to the SQLite WAL
        # asynchronously (~500ms after the JS call returns). Without a
        # brief wait here, the quit races the WAL write and the values
        # are lost on restart. 1.5 s is comfortably past the observed
        # ~500 ms flush window measured on macOS.
        time.sleep(1.5)

        app_state.quit()
        app_state.wait_quit(timeout_s=15)
        app_state.launch()
        app_state.wait_launched()

        # --- 5. F9 rediscover against the freshly-respawned sidecar -----
        #
        # New PID, new port, new basic-auth creds. Without this the next
        # http.get_config() would try to hit the dead sidecar.
        http.rediscover(app_state.sidecar_pid())

        # --- 6. Re-read via HTTP + DOM probe ----------------------------

        post_config = http.get_config()
        post_theme = _read_ls(dom, THEME_STORAGE_KEY)
        post_language = _read_ls(dom, LANGUAGE_STORAGE_KEY)

        # --- 7. Assert all three persisted ------------------------------

        assert post_config.get("model") == target_model, (
            f"model did not persist across restart: "
            f"got {post_config.get('model')!r}, expected {target_model!r}"
        )
        assert post_theme == target_theme, (
            f"theme did not persist across restart: "
            f"got {post_theme!r}, expected {target_theme!r}"
        )
        assert post_language is not None and target_language in post_language, (
            f"language did not persist across restart: "
            f"got {post_language!r}, expected contains {target_language!r}"
        )
    finally:
        # --- 8. Restore originals ---------------------------------------
        #
        # Run each restore independently so one failure doesn't skip the
        # others. localStorage writes are idempotent so they're safe to
        # issue unconditionally; the config PATCH is only re-sent if we
        # actually mutated it.
        try:
            _write_ls(dom, THEME_STORAGE_KEY, original_theme_raw)
        except Exception:
            pass
        try:
            _write_ls(dom, LANGUAGE_STORAGE_KEY, original_language_raw)
        except Exception:
            pass
        if config_patched:
            try:
                http.patch_config(original_config_snapshot)
            except Exception:
                pass
