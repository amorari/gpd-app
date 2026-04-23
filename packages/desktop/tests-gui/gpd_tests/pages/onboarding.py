"""Welcome-screen page object. Phase 3 onboarding flow uses this."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


def sentinel_path() -> Path:
    """Return the GPD onboarding sentinel path, honoring XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "gpd" / ".gpd-initialized"
    return Path.home() / ".config" / "gpd" / ".gpd-initialized"


class Onboarding:
    """Thin wrapper — probes welcome-screen state via DOMProbe.

    Presence checks use text from fixtures/en.json so they track locale
    drift. The API-key input/submit is driven via execute_js rather than
    AX, because the welcome form is a plain HTML input and execute_js
    keeps focus with the caller.
    """

    def __init__(self, mcp: Any) -> None:
        self._mcp = mcp
        self._probe = DOMProbe(mcp)

    @staticmethod
    def sentinel_present() -> bool:
        return sentinel_path().exists()

    def welcome_visible(self) -> bool:
        """True when the welcome title text is in the DOM."""
        from gpd_tests.helpers.selectors import TEXT_WELCOME_TITLE

        needle = TEXT_WELCOME_TITLE.replace('"', '\\"')
        try:
            return self._probe.eval_bool(
                f'!!document.body && document.body.innerText.includes("{needle}")'
            )
        except ProbeSkip:
            return False

    def enter_api_key(self, key: str) -> None:
        """Type `key` into the welcome API-key input and submit.

        Relies on the input being reachable via placeholder text. We use
        document.querySelector with an attribute match rather than a role
        selector so we don't require ARIA roles that may shift.

        Pre-sets the TOS-accepted localStorage key BEFORE submit so the
        product's welcome-screen shortcut (welcome-screen.tsx:49-62)
        auto-POSTs TOS acceptance server-side and calls onComplete
        directly, skipping the TOS click-wrap UI. Exercising all four
        TOS interactions (scroll both texts to bottom + check both boxes
        + click "I Agree") would need bespoke DOM driving for each, and
        this test's contract is "key entry reaches home", not
        "click-wrap works".

        Returns (result, actual_value) from JS and verifies the value was set.
        """
        from gpd_tests.helpers.selectors import TEXT_WELCOME_API_KEY_PROMPT

        placeholder = TEXT_WELCOME_API_KEY_PROMPT.replace("\\", "\\\\").replace(
            '"', '\\"'
        )
        safe_key = key.replace("\\", "\\\\").replace("'", "\\'")
        # Must match packages/app/src/components/tos-content.tsx:24 and :48.
        js = f"""
        (function() {{
          try {{
            localStorage.setItem("gpd.tos.acceptedVersion", "0.0-placeholder");
          }} catch (e) {{}}
          const inp = document.querySelector('input[placeholder="{placeholder}"]');
          if (!inp) return ['no-input', ''];
          const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
          ).set;
          nativeSetter.call(inp, '{safe_key}');
          inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
          const actualValue = inp.value;
          const form = inp.closest('form');
          if (form) {{
            form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
            return ['form-submitted', actualValue];
          }}
          const btn = inp.parentElement && inp.parentElement.querySelector('button');
          if (btn) {{
            btn.click();
            return ['button-clicked', actualValue];
          }}
          return ['no-submit-target', actualValue];
        }})()
        """
        raw = self._probe.eval(js)
        # DOMProbe.eval returns JS values round-tripped through JSON, so an
        # array literal arrives as a JSON string "[...,...]" — parse it back
        # before pattern-matching. Previously we only handled list/tuple and
        # raised "UI may have changed" on every successful submit.
        if isinstance(raw, str) and raw.startswith("["):
            import json as _json
            try:
                raw = _json.loads(raw)
            except _json.JSONDecodeError:
                pass
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            result, actual_value = raw[0], raw[1]
        else:
            result, actual_value = raw, None

        if result not in ("form-submitted", "button-clicked"):
            raise RuntimeError(
                f"welcome submit failed: {result!r} — UI may have changed"
            )
        if actual_value != key:
            raise RuntimeError(
                f"enter_api_key: input value mismatch — "
                f"expected {key!r}, got {actual_value!r}"
            )

    def wait_for_home(self, *, timeout_s: float = 20.0) -> None:
        """Wait for the welcome screen to disappear (sentinel appears)."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if sentinel_path().exists() and not self.welcome_visible():
                return
            time.sleep(0.2)
        raise TimeoutError(
            "welcome screen never transitioned to home within "
            f"{timeout_s}s"
        )
