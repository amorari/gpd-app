"""Drive Kobalte Select components via the real user path (click → pick → close).

Kobalte Select (see packages/ui/src/components/select.tsx) renders:

- A trigger button with ``data-slot="select-select-trigger"`` and
  ``role="combobox"``.
- A portaled content wrapper with ``data-component="select-content"``
  containing a listbox (``role="listbox"``, ``data-slot="select-select-content-list"``).
- Items with ``data-slot="select-select-item"`` and ``role="option"``; the
  visible label lives in ``[data-slot="select-select-item-label"]``.

The listbox mounts on open, is removed on close, and lives in a portal (not a
descendant of the trigger), so selector scoping must be *document-level*.

Example
-------

    from gpd_tests.helpers.dom_probe import DOMProbe
    from gpd_tests.helpers.kobalte import select_option

    probe = DOMProbe(mcp)
    assert select_option(probe, '[data-testid="theme-select"]', "Dark")
"""
from __future__ import annotations

import json
import time

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


def _wait(probe: DOMProbe, js_predicate: str, timeout_s: float, poll_s: float = 0.05) -> bool:
    """Poll *js_predicate* (a JS expression returning bool) until truthy or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if probe.eval_bool(js_predicate):
                return True
        except ProbeSkip:
            raise
        except Exception:
            return False
        time.sleep(poll_s)
    return False


def select_option(
    probe: DOMProbe,
    trigger_selector: str,
    option_text: str,
    timeout_s: float = 3.0,
) -> bool:
    """Open a Kobalte Select, click the option matching *option_text*, wait for close.

    Parameters
    ----------
    probe:
        A :class:`DOMProbe` wrapping the MCP webview bridge.
    trigger_selector:
        CSS selector resolving to the visible trigger button. Typically the
        caller passes a stable testid or a ``[data-slot="select-select-trigger"]``
        variant scoped to a surface.
    option_text:
        Exact text content of the option to click (trimmed, case-sensitive).
        Matched against ``[data-slot="select-select-item-label"]`` first, then
        the item's full ``textContent`` as a fallback.
    timeout_s:
        Per-phase timeout for (a) listbox mount and (b) listbox dismissal.

    Returns
    -------
    bool
        ``True`` if the trigger clicked, the listbox appeared, an option with
        the requested text was clicked, and the listbox subsequently closed.
        ``False`` on any missing element, missing option, or close timeout.

    Example
    -------

        probe = DOMProbe(mcp)
        ok = select_option(probe, '[data-testid="provider-select"]', "gpd")
        assert ok, "provider select did not commit"
    """
    trig = json.dumps(trigger_selector)
    wanted = json.dumps(option_text)

    # Phase 1 — click the trigger.
    clicked = probe.eval_bool(
        f"(() => {{"
        f"  const el = document.querySelector({trig});"
        f"  if (!el) return false;"
        f"  el.scrollIntoView({{block:'center'}});"
        f"  el.click();"
        f"  return true;"
        f"}})()"
    )
    if not clicked:
        return False

    # Phase 2 — wait for the portaled listbox to mount.
    listbox_js = (
        "document.querySelector("
        "'[role=\"listbox\"],"
        "[data-kobalte-select-content],"
        "[data-slot=\"select-select-content-list\"]'"
        ") !== null"
    )
    if not _wait(probe, listbox_js, timeout_s):
        return False

    # Phase 3 — click the option whose label / textContent matches.
    picked = probe.eval_bool(
        f"(() => {{"
        f"  const wanted = {wanted};"
        f"  const items = Array.from(document.querySelectorAll("
        f"    '[data-slot=\"select-select-item\"],[role=\"option\"]'"
        f"  ));"
        f"  const norm = (s) => (s || '').replace(/\\s+/g,' ').trim();"
        f"  let hit = items.find((it) => {{"
        f"    const lbl = it.querySelector('[data-slot=\"select-select-item-label\"]');"
        f"    return lbl && norm(lbl.textContent) === wanted;"
        f"  }});"
        f"  if (!hit) hit = items.find((it) => norm(it.textContent) === wanted);"
        f"  if (!hit) return false;"
        f"  hit.scrollIntoView({{block:'center'}});"
        f"  hit.click();"
        f"  return true;"
        f"}})()"
    )
    if not picked:
        return False

    # Phase 4 — wait for the listbox to unmount.
    closed_js = (
        "document.querySelector("
        "'[role=\"listbox\"],"
        "[data-kobalte-select-content],"
        "[data-slot=\"select-select-content-list\"]'"
        ") === null"
    )
    return _wait(probe, closed_js, timeout_s)
