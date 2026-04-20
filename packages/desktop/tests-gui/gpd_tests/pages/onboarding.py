"""Welcome-screen page object. Phase 3 onboarding flow uses this."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


SENTINEL = Path.home() / ".config/gpd/.gpd-initialized"


def sentinel_path() -> Path:
    """Return the XDG-aware path to the GPD onboarding sentinel file.

    Respects ``XDG_CONFIG_HOME`` if set, otherwise falls back to
    ``~/.config/gpd/.gpd-initialized``.
    """
    import os

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "gpd" / ".gpd-initialized"
    return SENTINEL


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
        return SENTINEL.exists()

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
        """
        from gpd_tests.helpers.selectors import TEXT_WELCOME_API_KEY_PROMPT

        placeholder = TEXT_WELCOME_API_KEY_PROMPT.replace("\\", "\\\\").replace(
            '"', '\\"'
        )
        safe_key = key.replace("\\", "\\\\").replace("'", "\\'")
        js = f"""
        (function() {{
          const inp = document.querySelector('input[placeholder="{placeholder}"]');
          if (!inp) return 'no-input';
          const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
          ).set;
          nativeSetter.call(inp, '{safe_key}');
          inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
          const form = inp.closest('form');
          if (form) {{
            form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
            return 'form-submitted';
          }}
          const btn = inp.parentElement && inp.parentElement.querySelector('button');
          if (btn) {{
            btn.click();
            return 'button-clicked';
          }}
          return 'no-submit-target';
        }})()
        """
        result = self._probe.eval(js)
        if result not in ("form-submitted", "button-clicked"):
            raise RuntimeError(
                f"welcome submit failed: {result!r} — UI may have changed"
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
