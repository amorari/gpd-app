# CL-D: Loading + Settings

## test_loading_redirects_to_home_within_deadline (BROKEN)

- **Failure message:**
  `Failed: loading did not transition to home within 10s; last url='tauri://localhost/loading'`
  (identical across surfaces-1.xml, surfaces-2.xml, surfaces-3.xml — 0/3 passed)

- **Test expects:** After `mcp.navigate("tauri://localhost/loading")`, within a 10 s
  deadline `mcp.current_url()` must end with `"/"`. The test assumes `/loading`
  auto-redirects to `/` in the main webview.

- **What `loading.tsx` actually does:**
  The entry splitter at `packages/desktop/src/entry.tsx` routes by pathname:
  ```ts
  if (location.pathname === "/loading") {
    import("./loading")
  } else {
    import("./")
  }
  ```
  `packages/desktop/src/loading.tsx` is a **pure splash UI** (Font + Splash + Progress)
  with no router, no `window.location` mutation, and no `navigate()` call. Its
  only side-effect toward transitioning out is at lines 56–61:
  ```ts
  createEffect(() => {
    if (phase() !== "done") return
    const timer = setTimeout(() => events.loadingWindowComplete.emit(null), 1000)
    onCleanup(() => clearTimeout(timer))
  })
  ```
  It emits a Tauri event `loading-window-complete` that is consumed by the Rust
  host (`packages/desktop/src-tauri/src/lib.rs:538,633` — `event_once_fut::<LoadingWindowComplete>`)
  to show the main window. The splash never performs a client-side redirect; in
  production `/loading` is a separate splash **window**, not a route the main
  webview ever sits on.

  Driving the main webview to `/loading` via `mcp.navigate` therefore unloads
  the app, loads the splash module, and sits there forever. The splash's
  `phase() === "done"` signal only fires when the Rust-side
  `commands.awaitInitialization` resolves — on an already-running main window
  that initialization has long since completed and there is no subscriber for
  the emitted event, so even the event path is a no-op.

- **Root cause:** Product-by-design: there is no `/loading → /` client-side
  redirect. The test's mental model (that `/loading` is a transient SPA route
  that settles on `/`) does not match how the desktop package is structured. The
  comment in `route_loading()` (`navigator.py:22–32`) already documents that
  `/loading` is transient and "may never be observable via polling", which
  contradicts the test's 10 s wait-for-home assertion.

- **Label:** BROKEN (harness-side — invalid test premise). Not a product
  regression.

- **Fix hint:** Remove or redesign the test. Options:
  1. Delete it — nothing in the real product exercises a main-window `/loading`
     visit. The splash is shown by the Rust host in its own window.
  2. If we want splash-window coverage, navigate a separate webview window and
     assert splash UI renders (not URL transition). Entry point would be
     verifying `loading.tsx` renders the Splash component and that
     `loadingWindowComplete` fires once Rust reports `phase === "done"`.
  3. If we only want to assert "main window lands on home after startup", drop
     the explicit `/loading` step and just assert `current_url().endswith("/")`
     within the deadline after launch.

## test_settings_opens_via_cmd_comma_and_closes_on_escape (FLAKY)

- **Pass rate:** 0/1 failing attempt, 2/3 skipped. From the flakiness report
  "2/27 passed" counts skips as non-failures across the 27-run suite; among
  surfaces iterations (the only ones that exercise the test) it actually
  produced **1 hard failure and 2 skips** — never a real pass in the
  three-iteration surfaces window.

- **Failure message (when it fails):**
  `Failed: settings dialog never appeared (General tab not found)`
  (surfaces-1.xml). Surfaces-2 and surfaces-3 instead produced
  `execute_js unavailable (Timeout waiting for JS execution: Timeout waiting
  for execute-js response)` and were recorded as skipped.

- **Suspected source of flakiness:** Multiple independent sources stacked:
  1. **Focus/activation race.** The test calls `ax.activate()` then immediately
     runs `osascript 'tell application "System Events" to keystroke ","
     using command down'`. There is no wait between activate and keystroke —
     macOS window-server activation is asynchronous, so the Cmd+, can land
     before the GPD webview is actually the key window. When it does, the
     shortcut goes to whatever app was frontmost at dispatch time.
  2. **Dialog-gated keybind handler.** `packages/app/src/context/command.tsx:358`:
     ```ts
     const handleKeyDown = (event: KeyboardEvent) => {
       if (suspended() || dialog.active) return
       ...
     }
     ```
     If *any* dialog (prior test residue, a toast/modal stack, or the
     previously-open settings dialog from an earlier `steals_focus` test) is
     still active, the Cmd+, handler bails before it can match the `mod+comma`
     keybind registered for `settings.open`. No menu-bar accelerator exists for
     this command — `packages/desktop/src/menu.ts` has no `,`-accelerated
     MenuItem — so the keybind handler is the *only* path.
  3. **execute_js bridge flake.** The probe (`DOMProbe.eval_bool`) times out
     intermittently on the tauri-plugin-mcp execute-js channel, converting
     real failures into skips. Seen on surfaces-2 and -3 — same test code,
     same machine, same run session. This pattern also shows up in the other
     execute_js-dependent surfaces tests (`test_home`, `test_session`,
     `test_dialog_open_or_create_project`) in the same XMLs, so it is a
     cross-test bridge issue rather than settings-specific.

- **Root cause:** Composite — product shortcut is present and wired
  (`mod+comma` → `settings.open` → `openSettings()` in
  `packages/app/src/pages/layout.tsx:1116–1120`, and the JS keydown listener
  in `packages/app/src/context/command.tsx:381–383` normalizes `","` → `"comma"`
  at `command.tsx:45`), but the **test harness has no settle-after-activate
  wait and no dialog-state precondition check**, and the underlying `execute_js`
  bridge loses responses on some iterations. So the product is fine; the test
  is under-synchronized and the MCP JS bridge is unreliable.

- **Label:** FLAKY (harness-side). Not a product regression.

- **Fix hint:**
  1. After `ax.activate()`, poll until GPD is frontmost (e.g.
     `System Events -> frontmost of process "GPD" is true`) or sleep ~200 ms
     before dispatching the keystroke.
  2. Before keystroking, assert there is no modal/dialog open via DOMProbe
     (`document.querySelector('[role="dialog"][data-state="open"]')` is
     `null`) — skip or reset state if one is present. Alternatively add an
     explicit "dismiss any open dialog" setup via ESC before the Cmd+,
     injection.
  3. Harden the DOMProbe skip policy — a 5 s execute_js timeout on surfaces
     should not be silent skip; consider one retry before skipping so a
     transient bridge hiccup does not hide real regressions.
  4. Optional product-side hardening (not required): add a `Cmd+,` accelerator
     on a "Preferences…" menu item in `packages/desktop/src/menu.ts` that
     triggers `settings.open`. This gives macOS a native Services-level
     accelerator that survives dialog suppression in `handleKeyDown`, and is
     the canonical macOS UX expectation anyway.

## Summary labels

| Test | Label | Product-side gap? |
|------|-------|-------------------|
| `test_loading_redirects_to_home_within_deadline` | BROKEN (harness) | No — test premise invalid; `/loading` is a splash window, not a redirecting SPA route |
| `test_settings_opens_via_cmd_comma_and_closes_on_escape` | FLAKY (harness) | No — keybind + handler verified; failure modes are activation race, dialog-gate, and execute_js bridge timeouts |

Neither failure suggests a real `regression_on_branch` or `real_bug`. Both are
harness issues. The only soft product-side suggestion is adding a native
"Preferences…" menu item with `Cmd+,` accelerator for UX parity, independent
of the test.
