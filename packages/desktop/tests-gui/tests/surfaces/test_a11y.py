"""Accessibility surface tests.

Covers four a11y contracts that are cheap to verify via the webview bridge
and independent of any specific route's content:

1. Every rendered ``<button>`` exposes an accessible name (textContent,
   aria-label, or aria-labelledby pointing to non-empty text).
2. Opened dialogs declare ``role="dialog"`` *and* an aria-labelledby that
   resolves to a non-empty title element.
3. Form inputs that accept user input have an associated label — via
   ``<label for=id>``, aria-label, or aria-labelledby.
4. Keyboard-focusable elements have a visible focus indicator (outline or
   box-shadow) after Tab navigation.

These tests intentionally probe the *home* surface (plus the settings
dialog for #2) because that is the one route guaranteed to mount in every
environment (no sidecar / project / onboarding dependencies).
"""
from __future__ import annotations

import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


_SETTINGS_GENERAL_TAB = "General"


# Shared JS predicate: returns true if ``el`` is visually/semantically hidden
# and should therefore be excluded from a11y audits. Covers:
#   - the ``hidden`` HTML attribute
#   - computed ``display: none``
#   - computed ``visibility: hidden``
#   - ``aria-hidden="true"`` on the element itself or on any ancestor
_JS_IS_HIDDEN = (
    'const isHidden = (el) => {'
    '  if (!el) return true;'
    '  if (el.hasAttribute && el.hasAttribute("hidden")) return true;'
    '  const cs = getComputedStyle(el);'
    '  if (cs && (cs.display === "none" || cs.visibility === "hidden")) return true;'
    '  let cur = el;'
    '  while (cur && cur.nodeType === 1) {'
    '    if (cur.getAttribute && cur.getAttribute("aria-hidden") === "true") return true;'
    '    cur = cur.parentElement;'
    '  }'
    '  return false;'
    '};'
)


def _dismiss_any_overlay(probe: DOMProbe, os_input, *, max_presses: int = 3) -> None:
    """Press Escape up to ``max_presses`` times to clear any dialog/popover/menu."""
    for _ in range(max_presses):
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


# ---------------------------------------------------------------------------
# 1. Buttons have accessible names
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_all_buttons_have_accessible_name(mcp, os_input):
    """Every ``<button>`` must expose an accessible name.

    A button is "nameless" if it has NONE of:
      - non-empty ``textContent`` (after trim)
      - a non-empty ``aria-label``
      - an ``aria-labelledby`` pointing to an element with non-empty text
      - a non-empty ``title`` (screen-readers fall back to title)

    We report the first 5 offenders in the failure message so regressions
    are actionable without digging through screenshots.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    # Be defensive about a stale overlay from a preceding test: bare icon
    # buttons inside the overlay shouldn't mask real regressions on home.
    _dismiss_any_overlay(probe, os_input)

    try:
        result = probe.eval(
            '(() => {'
            + _JS_IS_HIDDEN +
            '  const buttons = Array.from(document.querySelectorAll("button"))'
            '    .filter(b => !isHidden(b));'
            '  const bare = [];'
            '  for (const b of buttons) {'
            '    const text = (b.textContent || "").trim();'
            '    if (text) continue;'
            '    const aLabel = (b.getAttribute("aria-label") || "").trim();'
            '    if (aLabel) continue;'
            '    const labelledBy = (b.getAttribute("aria-labelledby") || "").trim();'
            '    if (labelledBy) {'
            '      const ids = labelledBy.split(/\\s+/);'
            '      let ok = false;'
            '      for (const id of ids) {'
            '        const ref = document.getElementById(id);'
            '        if (ref && (ref.textContent || "").trim()) { ok = true; break; }'
            '      }'
            '      if (ok) continue;'
            '    }'
            '    const titleAttr = (b.getAttribute("title") || "").trim();'
            '    if (titleAttr) continue;'
            '    if (bare.length < 5) {'
            '      bare.push({'
            '        tag: b.tagName,'
            '        cls: (b.className || "").toString().slice(0, 80),'
            '        id: b.id || "",'
            '        outer: (b.outerHTML || "").slice(0, 160)'
            '      });'
            '    }'
            '  }'
            '  return JSON.stringify({total: buttons.length, bare_count: bare.length, bare: bare});'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    import json as _json
    try:
        payload = _json.loads(result)
    except (TypeError, ValueError):
        pytest.skip(f"unexpected probe result shape: {result!r}")

    total = payload.get("total", 0)
    if total == 0:
        pytest.skip("no buttons found on home surface — render failure?")

    bare = payload.get("bare", [])
    assert not bare, (
        f"{payload.get('bare_count', len(bare))} of {total} buttons lack an "
        f"accessible name. First {len(bare)}:\n"
        + "\n".join(
            f"  - <{b['tag']}{' id=' + b['id'] if b.get('id') else ''} "
            f"class={b['cls']!r}>  {b['outer']}"
            for b in bare
        )
    )


# ---------------------------------------------------------------------------
# 2. Dialogs declare role + aria-labelledby
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_dialogs_have_role_dialog_or_aria_labelledby(mcp, ax, os_input):
    """Open the settings dialog via Cmd+, and verify:
      - ``[role="dialog"]`` is present
      - it carries an ``aria-labelledby`` attribute
      - the referenced element has non-empty text

    Uses the same F11 settle-wait + pre-dismiss sequence as
    ``test_dialog_settings.py`` so shared overlay state from sibling tests
    doesn't cause a false skip.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    ax.activate()
    time.sleep(0.15)

    probe = DOMProbe(mcp)

    # Clear any leftover dialog — command.tsx early-returns on Cmd+, when a
    # dialog is already mounted.
    try:
        dialog_open = probe.eval_bool(
            '(() => !!document.querySelector('
            '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if dialog_open:
        try:
            os_input.press_key("escape")
        except Exception:
            pass
        time.sleep(0.15)

    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "," using command down',
            ],
            check=True,
        )
    except Exception as e:
        pytest.skip(f"osascript Cmd+, failed ({e})")

    # Wait for the General tab as the presence signal.
    needle = _SETTINGS_GENERAL_TAB.replace('"', '\\"')
    deadline = time.monotonic() + 5.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                '(() => {'
                '  const tabs = Array.from(document.querySelectorAll('
                '    "[role=\\"tab\\"], [data-slot=\\"tabs-trigger\\"]"'
                '  ));'
                f'  return tabs.some(t => t.textContent.trim() === "{needle}");'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        if opened:
            break
        time.sleep(0.1)

    try:
        if not opened:
            pytest.fail("settings dialog never appeared (General tab not found)")

        try:
            result = probe.eval(
                '(() => {'
                '  const d = document.querySelector("[role=\\"dialog\\"]");'
                '  if (!d) return JSON.stringify({present: false});'
                '  const labelledBy = (d.getAttribute("aria-labelledby") || "").trim();'
                '  const aLabel = (d.getAttribute("aria-label") || "").trim();'
                '  let labelText = "";'
                '  if (labelledBy) {'
                '    const ids = labelledBy.split(/\\s+/);'
                '    for (const id of ids) {'
                '      const ref = document.getElementById(id);'
                '      if (ref) {'
                '        const t = (ref.textContent || "").trim();'
                '        if (t) { labelText = t; break; }'
                '      }'
                '    }'
                '  }'
                '  return JSON.stringify({'
                '    present: true,'
                '    labelledBy: labelledBy,'
                '    ariaLabel: aLabel,'
                '    labelText: labelText'
                '  });'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")

        import json as _json
        try:
            payload = _json.loads(result)
        except (TypeError, ValueError):
            pytest.skip(f"unexpected probe result shape: {result!r}")

        assert payload.get("present"), "no [role=dialog] found after opening settings"
        # Accept either aria-labelledby->text OR a direct aria-label as the
        # WAI-ARIA spec treats them as equivalent name sources.
        labelled_by = payload.get("labelledBy", "")
        label_text = payload.get("labelText", "")
        aria_label = payload.get("ariaLabel", "")
        assert labelled_by or aria_label, (
            "[role=dialog] has neither aria-labelledby nor aria-label"
        )
        if labelled_by:
            assert label_text, (
                f"aria-labelledby={labelled_by!r} does not resolve to an "
                "element with non-empty text"
            )
    finally:
        _dismiss_any_overlay(probe, os_input)


# ---------------------------------------------------------------------------
# 3. Form inputs have associated labels
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_form_inputs_have_associated_labels(mcp, os_input):
    """Every user-facing ``<input>`` must expose an accessible name.

    Excludes ``type="hidden"`` and ``type="submit"`` (submit buttons derive
    their name from ``value``), plus visually/semantically hidden inputs:
    the ``hidden`` attribute, ``display: none``, ``visibility: hidden``, or
    ``aria-hidden="true"`` on self or any ancestor. For each remaining
    input we accept:
      - a ``<label for=id>`` in the document
      - an ancestor ``<label>`` wrapping the input
      - a non-empty ``aria-label``
      - an ``aria-labelledby`` pointing to non-empty text
      - a non-empty ``placeholder`` (degraded but common for search fields)
      - a non-empty ``title``
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    _dismiss_any_overlay(probe, os_input)

    try:
        result = probe.eval(
            '(() => {'
            + _JS_IS_HIDDEN +
            '  const inputs = Array.from(document.querySelectorAll('
            '    "input:not([type=\\"hidden\\"]):not([type=\\"submit\\"])"'
            '  )).filter(inp => !isHidden(inp));'
            '  const bare = [];'
            '  for (const inp of inputs) {'
            '    const id = inp.id || "";'
            '    if (id && document.querySelector("label[for=\\"" + id.replace(/"/g, "\\\\\\"") + "\\"]")) continue;'
            '    if (inp.closest("label")) continue;'
            '    const aLabel = (inp.getAttribute("aria-label") || "").trim();'
            '    if (aLabel) continue;'
            '    const labelledBy = (inp.getAttribute("aria-labelledby") || "").trim();'
            '    if (labelledBy) {'
            '      const ids = labelledBy.split(/\\s+/);'
            '      let ok = false;'
            '      for (const lid of ids) {'
            '        const ref = document.getElementById(lid);'
            '        if (ref && (ref.textContent || "").trim()) { ok = true; break; }'
            '      }'
            '      if (ok) continue;'
            '    }'
            '    const placeholder = (inp.getAttribute("placeholder") || "").trim();'
            '    if (placeholder) continue;'
            '    const titleAttr = (inp.getAttribute("title") || "").trim();'
            '    if (titleAttr) continue;'
            '    if (bare.length < 5) {'
            '      bare.push({'
            '        type: inp.getAttribute("type") || "text",'
            '        id: id,'
            '        name: inp.getAttribute("name") || "",'
            '        outer: (inp.outerHTML || "").slice(0, 160)'
            '      });'
            '    }'
            '  }'
            '  return JSON.stringify({total: inputs.length, bare_count: bare.length, bare: bare});'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    import json as _json
    try:
        payload = _json.loads(result)
    except (TypeError, ValueError):
        pytest.skip(f"unexpected probe result shape: {result!r}")

    total = payload.get("total", 0)
    if total == 0:
        pytest.skip("no user-facing <input> elements on home surface")

    bare = payload.get("bare", [])
    assert not bare, (
        f"{payload.get('bare_count', len(bare))} of {total} inputs lack an "
        f"associated label. First {len(bare)}:\n"
        + "\n".join(
            f"  - <input type={b['type']!r}"
            + (f" id={b['id']!r}" if b['id'] else "")
            + (f" name={b['name']!r}" if b['name'] else "")
            + f">  {b['outer']}"
            for b in bare
        )
    )


# ---------------------------------------------------------------------------
# 4. Focus indicator is visible
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_focusable_elements_have_visible_outline(mcp, os_input):
    """After 3 Tab presses, the active element must show a focus indicator.

    Accept any of:
      - ``outlineStyle !== "none"`` AND ``outlineWidth`` > 0
      - ``boxShadow`` differs from the default ``"none"``
      - ``outlineColor`` is a non-transparent ring (fallback for rings via
        tailwind that use ``outline`` rather than shadow)

    We bail out if the body never had a focusable element (e.g. the app
    rendered a loading shimmer and nothing tab-reachable exists yet).
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    _dismiss_any_overlay(probe, os_input)

    # Move focus into the document deterministically before tabbing, so the
    # first Tab doesn't get swallowed by macOS's "focus the window chrome"
    # behavior.
    try:
        probe.eval(
            '(() => {'
            '  if (document.body) { document.body.focus(); }'
            '  return "ok";'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    for _ in range(3):
        try:
            os_input.press_key("tab")
        except Exception as e:
            pytest.skip(f"os_input.press_key unavailable ({e})")
        time.sleep(0.1)

    try:
        result = probe.eval(
            '(() => {'
            '  const el = document.activeElement;'
            '  if (!el || el === document.body) {'
            '    return JSON.stringify({reachable: false});'
            '  }'
            '  const cs = getComputedStyle(el);'
            '  return JSON.stringify({'
            '    reachable: true,'
            '    tag: el.tagName,'
            '    outlineStyle: cs.outlineStyle,'
            '    outlineWidth: cs.outlineWidth,'
            '    outlineColor: cs.outlineColor,'
            '    boxShadow: cs.boxShadow'
            '  });'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable mid-test ({e})")

    import json as _json
    try:
        payload = _json.loads(result)
    except (TypeError, ValueError):
        pytest.skip(f"unexpected probe result shape: {result!r}")

    if not payload.get("reachable"):
        pytest.skip(
            "no tab-reachable element after 3 Tab presses — "
            "home surface may not expose interactive controls yet"
        )

    outline_style = str(payload.get("outlineStyle", "none")).lower()
    outline_width = str(payload.get("outlineWidth", "0px"))
    box_shadow = str(payload.get("boxShadow", "none")).lower()

    def _px_gt_zero(v: str) -> bool:
        # outlineWidth comes back like "2px" or "0px"
        try:
            return float(v.rstrip("px")) > 0.0
        except ValueError:
            return False

    outline_ok = outline_style != "none" and _px_gt_zero(outline_width)
    shadow_ok = box_shadow not in ("none", "")

    assert outline_ok or shadow_ok, (
        f"active <{payload.get('tag')}> lacks a visible focus indicator: "
        f"outlineStyle={outline_style!r} outlineWidth={outline_width!r} "
        f"boxShadow={box_shadow!r}"
    )
