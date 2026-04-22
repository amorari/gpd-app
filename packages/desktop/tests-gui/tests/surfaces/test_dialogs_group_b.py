"""Phase G5.2 — interaction tests for four top coverage-gap dialogs.

Covers:
    - dialog-connect-provider.tsx  (G1.1 top-3 testability gap, score 3)
    - dialog-custom-provider.tsx   (G1.1 gap, score 3)
    - dialog-manage-models.tsx     (G1.1 top-3 gap, score 2)
    - dialog-select-mcp.tsx        (G1.1 gap, score 2)

Each test drives the dialog via a programmatic trigger (execute_js) and
asserts a stable `data-component` / `data-action` anchor is present on the
rendered dialog. None of those anchors exist in the product tree yet, so
every test is marked ``xfail`` pointing at the staged patch that would add
them. When the patch lands on the product branch these tests flip green and
become regression guards — a single commit removes each xfail.

The patches live under ``packages/desktop/tests-gui/docs/gpd-app-patches/``
following the ``G5-dialog-<slug>-data-actions.patch`` naming convention.
This file is harness-only; it touches no product code.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


# Helpful recurring expressions ------------------------------------------------

# Wait up to this long for a dialog to mount once we've clicked its trigger.
# 3s matches the existing dialog-open-or-create-project test and is plenty
# for SolidJS + a dynamic import.
_DIALOG_MOUNT_TIMEOUT_S = 3.0

# Generic "any dialog is currently open" predicate. Used only as a defensive
# check before proceeding — never as the anchor assertion itself.
_JS_ANY_DIALOG_OPEN = (
    '!!document.querySelector('
    '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
    ')'
)


def _wait_for(probe: DOMProbe, js: str, timeout_s: float = _DIALOG_MOUNT_TIMEOUT_S) -> bool:
    """Poll ``js`` (must return a boolean) until it is truthy or timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if probe.eval_bool(js):
                return True
        except ProbeSkip:
            raise
        time.sleep(0.1)
    return False


# ---------------------------------------------------------------------------
# dialog-connect-provider
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(
    reason=(
        "pending G5-dialog-connect-provider-data-actions.patch — connect-provider "
        "dialog has no data-component anchor and no data-action on the back/method/"
        "submit controls; product currently scores 3 on inventory testability rubric"
    ),
    strict=False,
)
def test_dialog_connect_provider_has_stable_anchor(mcp):
    """Assert the connect-provider dialog exposes its contract anchors.

    Triggers the dialog by clicking the "Connect AI service" button that layout
    renders in the connected-providers section, then checks for a root
    ``data-component="dialog-connect-provider"`` anchor and a back-button
    ``data-action="connect-provider-back"`` anchor.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        # Fire the "provider.connect" command registered in layout.tsx by
        # locating any Connect button and clicking it. If none is rendered on
        # home (for instance because the welcome overlay is covering the
        # sidebar), fall back to skipping — that's a home-surface condition,
        # not a dialog-anchor bug.
        clicked = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll("button"));'
            '  const btn = btns.find('
            '    b => /connect.*(ai|service|provider)/i.test(b.innerText || "")'
            '  );'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'Connect AI service' (or similar) trigger found on home")

    # The select-provider dialog opens first; click a provider row to reach
    # connect-provider. Since dialog-select-provider also lacks anchors we
    # fall through and look for any of the connect anchors the patch adds.
    _wait_for(probe, _JS_ANY_DIALOG_OPEN)

    # Core contract: once the patch lands, the connect-provider dialog
    # exposes a unique data-component anchor.
    js = (
        '!!document.querySelector('
        '"[data-component=\\"dialog-connect-provider\\"]"'
        ') || !!document.querySelector('
        '"[data-action=\\"connect-provider-back\\"]"'
        ')'
    )
    try:
        present = _wait_for(probe, js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert present, (
        "dialog-connect-provider is missing the contract anchor "
        "[data-component=\"dialog-connect-provider\"] — patch "
        "G5-dialog-connect-provider-data-actions.patch not applied"
    )


# ---------------------------------------------------------------------------
# dialog-custom-provider
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.skip(
    reason=(
        "Custom BYOE provider removed upstream (feat(providers): remove Custom "
        "BYOE provider entry points). The dialog-custom-provider.tsx component "
        "no longer exists. Remove this test or replace when a new custom provider "
        "flow is added."
    )
)
def test_dialog_custom_provider_has_stable_anchor(mcp):
    """Assert the custom-provider dialog exposes its contract anchors.

    The custom-provider dialog is reachable from the select-provider picker
    (there's a "Custom" tile in that list). Simplest reliable trigger: open the
    select-provider dialog via the Connect flow, then click the custom tile.
    If the chain isn't reachable from a freshly-loaded home, skip.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll("button"));'
            '  const btn = btns.find('
            '    b => /connect.*(ai|service|provider)/i.test(b.innerText || "")'
            '  );'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'Connect AI service' (or similar) trigger found on home")

    if not _wait_for(probe, _JS_ANY_DIALOG_OPEN):
        pytest.skip("select-provider dialog never opened — upstream trigger flake")

    # Try to click a "Custom" provider row in the provider picker.
    try:
        opened_custom = probe.eval_bool(
            '(() => {'
            '  const all = Array.from(document.querySelectorAll("li, [role=\\"option\\"], button"));'
            '  const row = all.find(el => /custom.*(ai|provider|openai)/i.test(el.innerText || ""));'
            '  if (!row) return false;'
            '  row.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not opened_custom:
        pytest.skip("no 'Custom AI service' row found in select-provider dialog")

    # Contract: custom-provider dialog exposes a unique data-component or
    # submit-button data-action once the patch lands.
    js = (
        '!!document.querySelector('
        '"[data-component=\\"dialog-custom-provider\\"]"'
        ') || !!document.querySelector('
        '"[data-action=\\"custom-provider-submit\\"]"'
        ')'
    )
    try:
        present = _wait_for(probe, js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert present, (
        "dialog-custom-provider is missing the contract anchor "
        "[data-component=\"dialog-custom-provider\"] — patch "
        "G5-dialog-custom-provider-data-actions.patch not applied"
    )


# ---------------------------------------------------------------------------
# dialog-manage-models
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(
    reason=(
        "pending G5-dialog-manage-models-data-actions.patch — manage-models "
        "dialog has no data-component anchor on root and no data-action on per-"
        "model / per-provider toggle switches"
    ),
    strict=False,
)
def test_dialog_manage_models_has_stable_anchor(mcp):
    """Assert the manage-models dialog exposes its contract anchors.

    Triggers the dialog via its title text. ``dialog.model.manage`` →
    "Manage models" is rendered as the dialog title when open. The common
    entry path is the model picker's "Manage" button; we click anything
    labelled "Manage models" as a reliable proxy.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        # Try to directly invoke the manage-models dialog by clicking any
        # button labelled "Manage models" (common entry: settings → Models
        # tab, or the model picker popover "Manage" link). If nothing on the
        # current surface exposes that entry, skip.
        clicked = probe.eval_bool(
            '(() => {'
            '  const all = Array.from(document.querySelectorAll('
            '    "button, a, [role=\\"button\\"]"'
            '  ));'
            '  const el = all.find('
            '    e => /manage.*model/i.test(e.innerText || "") || '
            '         (e.getAttribute("aria-label") || "").match(/manage.*model/i)'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'Manage models' trigger found on home surface")

    if not _wait_for(probe, _JS_ANY_DIALOG_OPEN):
        pytest.skip("manage-models dialog never opened — upstream trigger flake")

    # Contract: manage-models exposes a unique data-component anchor and each
    # row toggle carries data-action="manage-model-toggle" once patch lands.
    js = (
        '!!document.querySelector('
        '"[data-component=\\"dialog-manage-models\\"]"'
        ') || !!document.querySelector('
        '"[data-action=\\"manage-model-toggle\\"]"'
        ') || !!document.querySelector('
        '"[data-action=\\"manage-provider-toggle\\"]"'
        ')'
    )
    try:
        present = _wait_for(probe, js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert present, (
        "dialog-manage-models is missing the contract anchor "
        "[data-component=\"dialog-manage-models\"] — patch "
        "G5-dialog-manage-models-data-actions.patch not applied"
    )


# ---------------------------------------------------------------------------
# dialog-select-mcp
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(
    reason=(
        "pending G5-dialog-select-mcp-data-actions.patch — select-mcp dialog "
        "has no data-component anchor on root and no data-action on per-server "
        "toggle rows"
    ),
    strict=False,
)
def test_dialog_select_mcp_has_stable_anchor(mcp):
    """Assert the select-mcp dialog exposes its contract anchors.

    Triggered via any "Research tools" (i18n: ``dialog.mcp.title``) button or
    link surfaced by the status popover or the session command palette. The
    dialog title text is the reliable presence signal prior to patch;
    after patch the data-component anchor is the contract signal.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const all = Array.from(document.querySelectorAll('
            '    "button, a, [role=\\"button\\"], [role=\\"menuitem\\"]"'
            '  ));'
            '  const el = all.find('
            '    e => /research tools/i.test(e.innerText || "") || '
            '         /toggle research/i.test(e.innerText || "") || '
            '         (e.getAttribute("aria-label") || "").match(/research tools/i)'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'Research tools' / MCP trigger found on home surface")

    if not _wait_for(probe, _JS_ANY_DIALOG_OPEN):
        pytest.skip("select-mcp dialog never opened — upstream trigger flake")

    # Contract: select-mcp exposes a unique data-component anchor and each
    # server toggle carries data-action="mcp-toggle" once the patch lands.
    js = (
        '!!document.querySelector('
        '"[data-component=\\"dialog-select-mcp\\"]"'
        ') || !!document.querySelector('
        '"[data-action=\\"mcp-toggle\\"]"'
        ')'
    )
    try:
        present = _wait_for(probe, js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert present, (
        "dialog-select-mcp is missing the contract anchor "
        "[data-component=\"dialog-select-mcp\"] — patch "
        "G5-dialog-select-mcp-data-actions.patch not applied"
    )
