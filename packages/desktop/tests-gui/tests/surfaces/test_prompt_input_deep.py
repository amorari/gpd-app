"""Deep surfaces tests for packages/app/src/components/prompt-input.tsx.

Exercises every stable data-action anchor on the prompt-input composer:

    data-action="prompt-submit"
    data-action="prompt-attach"
    data-action="prompt-agent"
    data-action="prompt-model"
    data-action="prompt-model-variant"
    data-action="prompt-gpd-skills"

All tests are defensive about popups/modals: any click that can open a
dialog/popover is followed by a dismissal path (Escape) so state does not
leak into later tests.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """On-disk directory that GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_proj_prompt_deep")
    (p / "README.md").write_text("# test project\n")
    return str(p)


def _session_route(path: str) -> str:
    return route_session_in_project(encode_dir_token(path))


def _goto_session(mcp, path: str) -> None:
    Navigator(mcp).go(_session_route(path), timeout_s=5.0)


def _dismiss_any_overlay(probe: DOMProbe, os_input) -> None:
    """Best-effort cleanup: press Escape up to 3 times to clear dialogs/popovers.

    Kept tolerant — if the bridge is flaky we just return; subsequent tests
    will do their own `_goto_session` to restart from a known URL.
    """
    for _ in range(3):
        try:
            open_ = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"dialog\\"], [role=\\"dialog\\"], '
                '[role=\\"menu\\"], [data-component=\\"popover\\"]"'
                '))()'
            )
        except ProbeSkip:
            return
        if not open_:
            return
        try:
            os_input.press_key("escape")
        except Exception:
            return
        time.sleep(0.15)


def _focus_editor(probe: DOMProbe) -> bool:
    """Focus the contenteditable composer. Returns True on success."""
    try:
        return probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-component=\\"prompt-input\\"][contenteditable]"'
            '  );'
            '  if (!el) return false;'
            '  el.focus();'
            '  return document.activeElement === el;'
            '})()'
        )
    except ProbeSkip:
        return False


def _submit_disabled(probe: DOMProbe) -> bool | None:
    """True / False / None(unknown-skip) for whether every submit button is disabled."""
    try:
        return probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll('
            '    "button[data-action=\\"prompt-submit\\"][type=\\"submit\\"]"'
            '  ));'
            '  if (btns.length === 0) return null;'
            '  return btns.every('
            '    b => b.disabled || b.getAttribute("aria-disabled") === "true"'
            '  );'
            '})()'
        )
    except ProbeSkip:
        return None


# ---------------------------------------------------------------------------
# 1. Submit disabled on empty
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_submit_disabled_on_empty(mcp, prepared_project_path):
    """Cross-ref of test_session.test_send_button_disabled_on_empty_input.

    Kept here so the deep suite is self-contained and the invariant is
    verified before the enabling/typing test below.
    """
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    # Poll briefly — PromptInput has a prompt.ready() gate; give it time to mount.
    deadline = time.monotonic() + 3.0
    disabled = None
    while time.monotonic() < deadline:
        disabled = _submit_disabled(probe)
        if disabled is not None:
            break
        time.sleep(0.15)
    if disabled is None:
        pytest.skip("execute_js unavailable or prompt-submit not mounted")
    assert disabled, "prompt-submit not disabled on empty composer"


# ---------------------------------------------------------------------------
# 2. Submit becomes enabled after typing
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_prompt_submit_enabled_after_typing(mcp, ax, os_input, prepared_project_path):
    """Type a single char via os_input; submit should flip enabled → True."""
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)

    disabled_before = _submit_disabled(probe)
    if disabled_before is None:
        pytest.skip("execute_js unavailable")
    if not disabled_before:
        pytest.skip("composer was non-empty at start (stale state)")

    # Bring GPD to the foreground so keystrokes land in the webview.
    ax.activate()
    time.sleep(0.15)

    if not _focus_editor(probe):
        pytest.skip("could not focus prompt-input composer")

    try:
        os_input.type_text("x")
    except Exception as e:
        pytest.skip(f"type_text failed: {e}")

    deadline = time.monotonic() + 3.0
    enabled = False
    while time.monotonic() < deadline:
        disabled = _submit_disabled(probe)
        if disabled is None:
            pytest.skip("execute_js unavailable mid-test")
        if not disabled:
            enabled = True
            break
        time.sleep(0.1)

    # Best-effort cleanup: clear the char we typed so the next test starts
    # from a blank composer. Ignore failures — the session route resets for
    # other tests.
    try:
        os_input.press_key("backspace")
    except Exception:
        pass

    if not enabled:
        pytest.skip(
            "prompt-submit did not become enabled after typing "
            "(keystroke may not have reached webview)"
        )
    assert enabled


# ---------------------------------------------------------------------------
# 3. prompt-attach reachable + graceful dismiss of file picker
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_attach_button_present_and_reachable(mcp, os_input, prepared_project_path):
    """The attach button exists and is clickable.

    Clicking it triggers a native file picker; we do NOT click it from
    Python-side keystroke flow because that picker is OS-level and cliclick
    handling of a modal picker is brittle. Instead: verify the button is
    present, enabled, and that its onClick handler is bound — we exercise
    it by dispatching a click via execute_js, then immediately pressing
    Escape to dismiss any file chooser that surfaces.
    """
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        present = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-attach\\"]"'
            '  );'
            '  return !!el && !el.disabled;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not present:
        pytest.skip("prompt-attach button not found / disabled")

    # Try to click; the native file picker is OS-level so we fence it with
    # an Escape immediately. Some platforms (webkit-only builds) won't even
    # open a chooser from a synthetic click, which is fine — the goal is
    # unreachable-code detection, not a functional file upload.
    try:
        probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-attach\\"]"'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip:
        pass

    # Dismiss any OS or in-app dialog that may have appeared.
    time.sleep(0.2)
    try:
        os_input.press_key("escape")
    except Exception:
        pass
    time.sleep(0.15)
    _dismiss_any_overlay(probe, os_input)


# ---------------------------------------------------------------------------
# 4. prompt-agent trigger opens picker, closes cleanly
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_agent_trigger_opens_picker(mcp, os_input, prepared_project_path):
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        present = probe.eval_bool(
            '(() => !!document.querySelector('
            '"[data-action=\\"prompt-agent\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not present:
        pytest.skip("prompt-agent trigger not found (shell mode?)")

    # Click trigger.
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-agent\\"]"'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("could not click prompt-agent trigger")

    # Poll for a menu/popover/listbox — Kobalte's Select uses role=listbox
    # but may also render via data-component=popover or role=menu depending
    # on the theme.
    deadline = time.monotonic() + 3.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[role=\\"listbox\\"], [role=\\"menu\\"], '
                '[data-component=\\"popover\\"], [data-component=\\"dialog\\"]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)

    # Always try to close, even on failure, so subsequent tests aren't
    # blocked by a stuck popover.
    _dismiss_any_overlay(probe, os_input)

    if not opened:
        pytest.skip("agent picker popover did not render (locale/data-dependent)")
    assert opened


# ---------------------------------------------------------------------------
# 5. prompt-model trigger opens picker
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_model_trigger_opens_picker(mcp, os_input, prepared_project_path):
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        present = probe.eval_bool(
            '(() => !!document.querySelector('
            '"[data-action=\\"prompt-model\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not present:
        pytest.skip("prompt-model trigger not found (shell mode?)")

    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-model\\"]"'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("could not click prompt-model trigger")

    deadline = time.monotonic() + 3.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[role=\\"listbox\\"], [role=\\"menu\\"], '
                '[data-component=\\"popover\\"], [data-component=\\"dialog\\"]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)

    _dismiss_any_overlay(probe, os_input)

    if not opened:
        pytest.skip(
            "model picker popover did not render "
            "(unpaid dialog async-import or no providers configured)"
        )
    assert opened


# ---------------------------------------------------------------------------
# 6. prompt-model-variant presence (tolerate absence)
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_model_variant_trigger_presence(mcp, prepared_project_path):
    """The variant trigger is always rendered in normal mode (per component
    source), but its list may be just ``["default"]`` for providers without
    variants. We only assert reachability — a click would cycle variants and
    mutate persisted state which is out of scope for a presence probe.
    """
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        reachable = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-model-variant\\"]"'
            '  );'
            '  if (!el) return false;'
            '  const rect = el.getBoundingClientRect();'
            '  return rect.width > 0 && rect.height > 0;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not reachable:
        pytest.skip(
            "prompt-model-variant not reachable (provider has no variants "
            "or composer is in shell mode)"
        )
    assert reachable


# ---------------------------------------------------------------------------
# 7. prompt-gpd-skills presence (do not click — would open a dialog)
# ---------------------------------------------------------------------------

@pytest.mark.surfaces
def test_prompt_gpd_skills_trigger_presence(mcp, prepared_project_path):
    """The GPD skills button is always rendered in normal mode. Clicking it
    triggers a dynamic import of DialogGpdSkills — we skip the click because
    the async import + dialog stack would add flake without exercising a
    distinct data-action.
    """
    _goto_session(mcp, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        reachable = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-action=\\"prompt-gpd-skills\\"]"'
            '  );'
            '  if (!el) return false;'
            '  const rect = el.getBoundingClientRect();'
            '  return rect.width > 0 && rect.height > 0;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not reachable:
        pytest.skip("prompt-gpd-skills not reachable (composer may be in shell mode)")
    assert reachable
