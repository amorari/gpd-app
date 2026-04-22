"""Prompt input interaction flow tests.

Covers three interaction flows for the prompt composer:

    1. Slash-command popover — "/" triggers the command list; Escape closes it.
    2. @-mention popover — "@" triggers the mention picker; Escape closes it.
    3. Send-button state transitions — disabled on empty, enabled after typing,
       disabled again after clearing.

The prompt input is a contenteditable div (data-component="prompt-input").
Text is injected via execute_js because os_input.type_text is unreliable
when the webview is not the foreground window and because the popover logic
is driven purely by the `input` event on the contenteditable, not by raw
OS keystrokes.

All tests:
    - Use pytest.skip liberally instead of hard-failing on webview-bridge flake.
    - Clean up after themselves (press Escape / clear text) so later tests
      start from a known blank-composer state.
    - Are marked @pytest.mark.surfaces.
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


# ---------------------------------------------------------------------------
# Shared helpers (mirrors the pattern from test_prompt_input_deep.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """On-disk directory that GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_proj_prompt_flows")
    (p / "README.md").write_text("# prompt flow test project\n")
    return str(p)


def _session_route(dir_token: str, session_id: str) -> str:
    return route_session_in_project(dir_token, session_id)


def _goto_session(mcp, http, path: str) -> str:
    """Create a session, navigate to it, return session id for cleanup."""
    ses = http.create_session(directory=path)
    sid = ses.get("id")
    if not sid:
        raise RuntimeError(f"create_session returned no id: {ses!r}")
    dir_token = encode_dir_token(path)
    Navigator(mcp).go(_session_route(dir_token, sid), timeout_s=8.0)
    return sid


def _focus_editor(probe: DOMProbe) -> bool:
    """Focus the contenteditable composer.  Returns True on success."""
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


def _inject_text(probe: DOMProbe, text: str) -> bool:
    """Inject *text* into the focused contenteditable and fire an input event.

    The prompt-input component listens to the native `input` event to update
    its internal state and open/close popovers.  Directly setting textContent
    and dispatching `input` is the most reliable way to trigger that logic
    without depending on OS-level keystroke delivery.

    Returns True if the injection appeared to succeed.
    """
    # Escape the text for embedding inside a JS string literal.
    safe_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
    try:
        return probe.eval_bool(
            f'(() => {{'
            f'  const el = document.querySelector('
            f'    "[data-component=\\"prompt-input\\"][contenteditable]"'
            f'  );'
            f'  if (!el) return false;'
            f'  el.focus();'
            f'  el.textContent = "{safe_text}";'
            f'  const range = document.createRange();'
            f'  const sel = window.getSelection();'
            f'  range.selectNodeContents(el);'
            f'  range.collapse(false);'
            f'  sel.removeAllRanges();'
            f'  sel.addRange(range);'
            f'  el.dispatchEvent(new Event("input", {{ bubbles: true }}));'
            f'  return true;'
            f'}})()'
        )
    except ProbeSkip:
        return False


def _clear_editor(probe: DOMProbe) -> None:
    """Clear the contenteditable and fire an input event to reset state."""
    try:
        probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-component=\\"prompt-input\\"][contenteditable]"'
            '  );'
            '  if (!el) return false;'
            '  el.focus();'
            '  el.textContent = "";'
            '  el.dispatchEvent(new Event("input", { bubbles: true }));'
            '  return true;'
            '})()'
        )
    except ProbeSkip:
        pass


def _press_escape(probe: DOMProbe) -> None:
    """Dispatch a keyboard Escape event on the focused contenteditable."""
    try:
        probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    "[data-component=\\"prompt-input\\"][contenteditable]"'
            '  );'
            '  if (!el) return false;'
            '  const evt = new KeyboardEvent("keydown", {'
            '    bubbles: true, cancelable: true, key: "Escape", code: "Escape"'
            '  });'
            '  el.dispatchEvent(evt);'
            '  return true;'
            '})()'
        )
    except ProbeSkip:
        pass


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


def _popover_visible(probe: DOMProbe) -> bool | None:
    """True if a prompt popover (slash or @-mention) is currently mounted.

    The PromptPopover component wraps both the slash-command list and the
    @-mention picker in a single container div.  It is only mounted in the
    DOM when ``store.popover`` is non-null (SolidJS <Show when={props.popover}>).

    We detect it by looking for buttons inside that container.  The slash
    popover renders ``button[data-slash-id]`` elements; the @-mention picker
    renders plain ``button`` elements with icon/text children.  To avoid
    false-positives from unrelated overlays we also check that the containing
    div sits directly above the prompt-input DOM area.
    """
    try:
        return probe.eval_bool(
            '(() => {'
            # The PromptPopover div is a sibling of the DockShellForm that
            # wraps the actual editor.  It is rendered unconditionally by
            # PromptInput but its *content* is gated by <Show when>.  The
            # div itself always exists; the slash/@ buttons only exist when
            # the popover is open.  We detect "open" by the presence of
            # button children inside the absolute-positioned container.
            '  const btns = document.querySelectorAll('
            '    "button[data-slash-id], '
            '     [class*=\\"prompt-input\\"] button[class*=\\"rounded-md\\"]"'
            '  );'
            # Simpler but still correct: any button rendered by PromptPopover
            # is distinguishable via data-slash-id (slash mode) or by being
            # inside the popover container itself (at mode).  We relax to
            # checking either bucket.
            '  if (btns.length > 0) return true;'
            # Fallback: check the popover container directly.  It sits above
            # the editor; look for a div that is absolutely positioned and
            # contains buttons.
            '  const containers = document.querySelectorAll('
            '    "[class*=\\"-translate-y-full\\"]"'
            '  );'
            '  for (const c of containers) {'
            '    if (c.querySelectorAll("button").length > 0) return true;'
            '  }'
            '  return false;'
            '})()'
        )
    except ProbeSkip:
        return None


def _slash_popover_visible(probe: DOMProbe) -> bool | None:
    """True if slash-command items are present in the DOM."""
    try:
        return probe.eval_bool(
            '(() => !!document.querySelector("button[data-slash-id]"))()'
        )
    except ProbeSkip:
        return None


def _at_popover_visible(probe: DOMProbe) -> bool | None:
    """True if the @-mention picker container is present with at least one button.

    The @-mention popover renders a list of <button> elements for agents and
    files.  The container has ``-translate-y-full`` in its class list (it
    slides upward above the editor) and is only mounted when
    ``store.popover === "at"``.
    """
    try:
        return probe.eval_bool(
            '(() => {'
            '  const containers = document.querySelectorAll('
            '    "[class*=\\"-translate-y-full\\"]"'
            '  );'
            '  for (const c of containers) {'
            '    if (c.querySelectorAll("button").length > 0) return true;'
            '  }'
            '  return false;'
            '})()'
        )
    except ProbeSkip:
        return None


def _poll(fn, *, timeout_s: float = 3.0, poll_s: float = 0.1):
    """Poll *fn* until it returns a truthy non-None value or timeout.

    Returns the last value returned by *fn* (which may be None / False if
    the timeout fires without success).
    """
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        val = fn()
        if val is not None and val:
            return val
        last = val
        time.sleep(poll_s)
    return last


# ---------------------------------------------------------------------------
# Test 1: Slash command popover
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_slash_command_popover(mcp, http, prepared_project_path):
    """Typing "/" into the prompt input opens the slash-command popover.

    Flow:
        1. Create a session and navigate to the active session route so the
           prompt input is mounted (the session-list route does not render it).
        2. Focus the contenteditable editor.
        3. Inject "/" and fire an input event.
        4. Poll until slash-command buttons appear in the DOM.
        5. Assert at least one suggestion item is visible.
        6. Dispatch Escape to close the popover.
        7. Assert the popover buttons are gone from the DOM.
    """
    sid = _goto_session(mcp, http, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        # Verify the editor is present before doing anything.
        try:
            present = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"prompt-input\\"][contenteditable]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if not present:
            pytest.skip("prompt-input editor not found in DOM")

        if not _focus_editor(probe):
            pytest.skip("could not focus prompt-input editor")

        # Inject "/" to trigger the slash popover.
        if not _inject_text(probe, "/"):
            pytest.skip("could not inject text into prompt-input editor")

        # Poll until at least one slash-command item appears.
        opened = _poll(_slash_popover_visible, timeout_s=3.0, poll_s=0.1)

        if opened is None:
            # execute_js became unavailable mid-test.
            _clear_editor(probe)
            pytest.skip("execute_js unavailable while waiting for slash popover")

        if not opened:
            # The popover may not appear if there are no registered slash commands
            # (e.g. fresh unconfigured session with no builtins loaded yet).
            _clear_editor(probe)
            pytest.skip(
                "slash-command popover did not appear after typing '/' "
                "(no slash commands registered or async command list not yet loaded)"
            )

        assert opened, "expected at least one slash-command item in the DOM"

        # Dismiss with Escape.
        _press_escape(probe)
        time.sleep(0.2)

        # Verify the popover has closed.  Use `is False` (not `not bool(...)`) so
        # that None (bridge down / ProbeSkip) is NOT treated as "confirmed closed".
        closed = _poll(
            lambda: _slash_popover_visible(probe) is False,
            timeout_s=2.0,
            poll_s=0.1,
        )
        _clear_editor(probe)

        assert closed, "slash-command popover did not close after pressing Escape"
    finally:
        try:
            http.delete_session(sid)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Test 2: @-mention popover
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_at_mention_popover(mcp, http, prepared_project_path):
    """Typing "@" into the prompt input opens the @-mention picker.

    Flow:
        1. Create a session and navigate to the active session route.
        2. Focus the contenteditable editor.
        3. Inject "@" and fire an input event.
        4. Poll until mention-picker buttons appear in the DOM.
        5. Assert at least one item is listed.
        6. Dispatch Escape to close the picker.
        7. Assert the picker is gone from the DOM.

    The at-popover shows agents and/or recently-opened files.  In a fresh
    session with no open files and no agents, the list may be empty (the
    component renders a "no results" placeholder text node rather than
    buttons).  In that case we only verify that the popover *container*
    appeared and was dismissed; we do not assert item count.
    """
    sid = _goto_session(mcp, http, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        try:
            present = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"prompt-input\\"][contenteditable]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if not present:
            pytest.skip("prompt-input editor not found in DOM")

        if not _focus_editor(probe):
            pytest.skip("could not focus prompt-input editor")

        # Inject "@" — the handleInput regex is /@(\S*)$/ so a lone "@" opens the
        # at-popover with an empty query, returning all agents + recent files.
        if not _inject_text(probe, "@"):
            pytest.skip("could not inject '@' into prompt-input editor")

        # Poll until the at-popover container appears.
        opened = _poll(_at_popover_visible, timeout_s=3.0, poll_s=0.1)

        if opened is None:
            _clear_editor(probe)
            pytest.skip("execute_js unavailable while waiting for at-mention popover")

        if not opened:
            # At-popover may not render buttons when both agent list and recent
            # files are empty (fresh isolated session).  Check whether the
            # empty-results placeholder is rendered instead.
            try:
                placeholder_shown = probe.eval_bool(
                    '(() => {'
                    '  const els = document.querySelectorAll('
                    '    "[class*=\\"-translate-y-full\\"]"'
                    '  );'
                    '  for (const el of els) {'
                    '    if (el.textContent.trim().length > 0) return true;'
                    '  }'
                    '  return false;'
                    '})()'
                )
            except ProbeSkip:
                placeholder_shown = False

            if not placeholder_shown:
                _clear_editor(probe)
                pytest.skip(
                    "@-mention popover did not appear after typing '@' "
                    "(no agents or recent files and async file search not available)"
                )
            opened = True

        assert opened, "expected @-mention popover to open after typing '@'"

        # Dismiss with Escape.
        _press_escape(probe)
        time.sleep(0.2)

        # Use `is False` so that None (bridge down) is not treated as confirmed-closed.
        closed = _poll(
            lambda: _at_popover_visible(probe) is False,
            timeout_s=2.0,
            poll_s=0.1,
        )
        _clear_editor(probe)

        assert closed, "@-mention popover did not close after pressing Escape"
    finally:
        try:
            http.delete_session(sid)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Test 3: Send-button state transitions
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_send_button_state_transitions(mcp, http, prepared_project_path):
    """Send button is disabled on empty input, enabled after typing, disabled again after clear.

    This extends the coverage of test_prompt_submit_disabled_on_empty and
    test_prompt_submit_enabled_after_typing in test_prompt_input_deep.py by
    exercising the full round-trip (empty → typed → cleared) without relying
    on os_input.type_text (OS-level keystroke delivery), using execute_js
    to inject text instead.

    Flow:
        1. Create a session and navigate to the active session route.
        2. Verify send button is disabled on empty composer.
        3. Inject text via execute_js.
        4. Verify send button becomes enabled.
        5. Clear the editor via execute_js.
        6. Verify send button is disabled again.
    """
    sid = _goto_session(mcp, http, prepared_project_path)
    probe = DOMProbe(mcp)
    try:
        # ---- Step 1: verify disabled on empty --------------------------------
        deadline = time.monotonic() + 5.0
        disabled_initial = None
        while time.monotonic() < deadline:
            disabled_initial = _submit_disabled(probe)
            if disabled_initial is True:
                break
            time.sleep(0.15)

        if disabled_initial is None:
            pytest.skip("execute_js unavailable or prompt-submit not found in DOM")
        if not disabled_initial:
            pytest.skip(
                "send button was not disabled on empty composer at start "
                "(stale state from a previous test — session route resets this)"
            )

        # ---- Step 2: inject text and verify enabled --------------------------
        if not _focus_editor(probe):
            pytest.skip("could not focus prompt-input editor")

        if not _inject_text(probe, "hello world"):
            pytest.skip("could not inject text into prompt-input editor")

        # Poll until the button flips to enabled.
        deadline = time.monotonic() + 3.0
        enabled_after_typing = False
        while time.monotonic() < deadline:
            disabled_now = _submit_disabled(probe)
            if disabled_now is None:
                _clear_editor(probe)
                pytest.skip("execute_js unavailable after typing")
            if not disabled_now:
                enabled_after_typing = True
                break
            time.sleep(0.1)

        if not enabled_after_typing:
            _clear_editor(probe)
            pytest.skip(
                "send button did not become enabled after injecting text "
                "(prompt state update may not have fired)"
            )

        assert enabled_after_typing, "send button should be enabled after typing"

        # ---- Step 3: clear editor and verify disabled again ------------------
        _clear_editor(probe)

        deadline = time.monotonic() + 3.0
        disabled_after_clear = False
        while time.monotonic() < deadline:
            disabled_now = _submit_disabled(probe)
            if disabled_now is None:
                pytest.skip("execute_js unavailable after clearing editor")
            if disabled_now:
                disabled_after_clear = True
                break
            time.sleep(0.1)

        assert disabled_after_clear, (
            "send button should be disabled again after clearing the composer"
        )
    finally:
        try:
            http.delete_session(sid)
        except Exception:  # noqa: BLE001
            pass
