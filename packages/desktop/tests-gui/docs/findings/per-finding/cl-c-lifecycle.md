# CL-C: Lifecycle failures

## Common root cause

The lifecycle failures are **not** the `HTTPClient.rediscover(pid)` gap flagged
in task #76 — the tests crash *before* the rediscover gap has a chance to
matter. The real primary cause is a **test-side API-signature bug** in
`test_session_list_persistence.py`: it calls `app_state.wait_quit(timeout=15)`
but the method is `wait_quit(*, timeout_s: float = 10.0)`. `timeout=` isn't a
valid keyword-only arg, so Python raises `TypeError` mid-test — between
`app_state.quit()` and `app_state.launch()`. The session-scoped `app_state`
fixture (in the root `conftest.py`) now holds a quit GPD. The next two
lifecycle tests' `http` fixture calls `app_state.sidecar_pid()` → `None` →
`AssertionError: opencode-cli sidecar never appeared`. That's the cascade
pattern seen in `lifecycle-1.xml`.

`lifecycle-2.xml` shows a *second-order* cascade: after the broken first
invocation left GPD/opencode-cli in an unclean state, the next pytest
invocation's session-scoped `app_state` fixture called `state.launch()` but
`open -a GPD.app` never produced a running pid (10 s timeout, `pids: none`).
All 3 tests error on session setup without even entering their bodies.

So the ordering of causes is:
1. `TypeError` on `wait_quit(timeout=15)` (harness bug, fixable in 30 s).
2. Cascading `http`-fixture setup errors within the same pytest run because
   the session-scoped `app_state` was left in a quit-not-relaunched state.
3. Cross-invocation carry-over: the bad state can prevent GPD from even
   launching on the next run (`lifecycle-2.xml`).
4. *Only then*, if the harness got this far, would the rediscover gap bite
   in `test_session_survives_quit_relaunch` and `test_sidecar_respawn` —
   because the `http` fixture is function-scoped (root conftest.py:202,
   `@pytest.fixture` with no scope= → function), but inside a single test
   body there's no re-discovery once GPD has been quit+relaunched or the
   sidecar SIGKILLed. The tests even call out this gap in their own comments
   (`test_session_persistence.py` L37-41; `test_sidecar_respawn.py` L41-44).

In the current runs, issues #1–#3 mask #4: we never observe a pure
rediscover-gap failure because the TypeError prevents getting there.

## Per-test breakdown

### test_session_list_persistence.py::test_multiple_sessions_persist

- **Failure message:**
  `TypeError: AppState.wait_quit() got an unexpected keyword argument 'timeout'. Did you mean 'timeout_s'?`
- **Where in the test it fails:** line 14,
  `app_state.wait_quit(timeout=15)` (between `quit()` on L13 and `launch()` on L15).
- **Why the fixture/client is in a bad state:** pure harness-side keyword
  mismatch. `AppState.wait_quit` is declared `def wait_quit(self, *, timeout_s: float = 10.0)`
  in `gpd_tests/pages/app_state.py:189`, which is keyword-only. The test
  passes `timeout=15`, which doesn't match. The `http` fixture itself is
  healthy at this point — the test body raises before it uses `http` again.
- **Label:** **test-bug (harness regression)** — wrong keyword arg.
  Deterministic. Nothing to do with rediscover.
- **Fix hint:** rename `timeout=15` → `timeout_s=15` on L14. Optionally
  use `app_state.wait_quit(timeout_s=15)` to match the pattern used
  in `test_session_persistence.py` L32.

### test_session_persistence.py::test_session_survives_quit_relaunch

- **Failure message:** `AssertionError: opencode-cli sidecar never appeared`
  (on `lifecycle-1.xml`); `RuntimeError: GPD failed to launch within 10.0s`
  (on `lifecycle-2.xml`). Both are **setup-phase errors in the `http` fixture
  / `app_state` session fixture**, not in the test body.
- **Where in the test it fails:** never enters the test body. On run 1 it
  fails at `conftest.py:214` (the `assert pid is not None` guard in the
  `http` fixture). On run 2 it fails at `conftest.py:158` (session-scoped
  `app_state` → `state.launch()` in `app_state.py:131`). Both are cascade
  effects from the preceding test's TypeError.
- **Why the fixture/client is in a bad state:**
  - Run 1: `test_multiple_sessions_persist` ran first (alphabetical order
    within the lifecycle dir), called `app_state.quit()`, then TypeError'd
    before `app_state.launch()`. The session-scoped `app_state` (root
    conftest.py:145) holds a quit GPD; `app_state.sidecar_pid()` returns
    None; `http` fixture asserts.
  - Run 2: the previous pytest invocation exited dirty; the next run's
    session fixture tried `open -a GPD.app` and GPD never came up
    (Launch-Services / macOS state quirk; 10 s timeout, zero matching pids).
- **Label:** **test-cascade / infra-fallout** (primary); the originally
  intended failure mode would have been **harness-gap (rediscover)** but we
  never reach it. If the TypeError were fixed this test would likely flip to
  demonstrating the rediscover gap on L42 (`http.messages(ses["id"])` after
  `app_state.launch()`), which the test's own comment (L37–41) explicitly
  anticipates.
- **Fix hint:** fix the TypeError first to unblock this test, then confirm
  whether this test then fails on the rediscover gap. If it does,
  implement `HTTPClient.rediscover(pid)` (see suggested fix path below)
  and have the test call it right after `app_state.wait_launched()` on L34.

### test_sidecar_respawn.py::test_sidecar_respawns_after_sigkill

- **Failure message:** same two-run pattern as above — run 1 fails at
  `conftest.py:214` (`assert pid is not None`) inside the `http` fixture;
  run 2 fails at `conftest.py:158` via `state.launch()` timeout.
- **Where in the test it fails:** never enters the test body.
- **Why the fixture/client is in a bad state:** identical cascade as
  `test_session_persistence` — the shared session-scoped `app_state`
  fixture was corrupted by the earlier TypeError (run 1) or by the unclean
  exit of the prior invocation (run 2).
- **Label:** **test-cascade / infra-fallout** (primary); intended failure
  mode would have been **harness-gap (rediscover)**. This test actually
  has the only in-file workaround attempt (L45–55: retry `http.health()`
  in a 15 s loop), but the workaround can't help because the fixture still
  points at the *old* port+creds; after SIGKILL, the new sidecar has a
  new port and new `OPENCODE_SERVER_PASSWORD`, and the same `httpx.Client`
  with stale auth will 401/ECONNREFUSED indefinitely, not just fail once.
- **Fix hint:** (a) fix TypeError in the other file to unblock this test;
  (b) add `HTTPClient.rediscover(pid)` and call it in the retry loop
  instead of `http.health()`, OR have the test re-acquire the `http` client
  by calling a helper that rebuilds it from the new pid.

## Suggested fix path

### 1. Immediate unblock (30 s, independent of rediscover)

Change `test_session_list_persistence.py` line 14:

```python
-    app_state.wait_quit(timeout=15)
+    app_state.wait_quit(timeout_s=15)
```

This alone converts lifecycle-1 from 1 failure + 2 cascade-errors into
1 real test result (this test) + 2 tests that run for the first time.
It also prevents the cross-invocation cascade seen in lifecycle-2.

### 2. Close the rediscover gap (task #76)

Add a `rediscover(pid)` method to `HTTPClient` in
`gpd_tests/drivers/opencode_http.py`. Sketch:

```python
def rediscover(self, pid: int | None = None, *, timeout_s: float = 15.0) -> None:
    """Re-probe port+creds after a sidecar restart.

    Closes the old httpx.Client, resolves new port via
    discover_sidecar_port(pid=...), new creds via
    discover_sidecar_credentials(pid=...), and rebuilds self._client
    pointing at the new base_url with the new HTTP Basic auth. Waits
    up to timeout_s for /global/health to answer before returning.
    """
    from gpd_tests.helpers.timings import wait_until

    new_port = discover_sidecar_port(pid=pid, timeout_s=timeout_s)
    if pid is None:
        # discover_sidecar_port may have picked a pid via pgrep; re-resolve it
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True, text=True, check=False,
        )
        pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        if not pids:
            raise RuntimeError("rediscover: opencode-cli not running")
        pid = pids[0]
    user, pw = discover_sidecar_credentials(pid)

    old = self._client
    self._client = httpx.Client(
        base_url=f"http://127.0.0.1:{new_port}",
        auth=(user, pw),
        timeout=old.timeout,
    )
    old.close()

    def _ready() -> bool:
        try:
            self.health()
            return True
        except Exception:
            return False

    if not wait_until(_ready, timeout_s=timeout_s):
        raise RuntimeError(
            f"rediscover: new sidecar at :{new_port} did not answer /global/health"
        )
```

### 3. Wire it into the root `http` fixture

In `conftest.py`, after `yield client`, no change is needed for the
cross-test path (fixture is function-scoped and rebuilds each test). The
gap is *within* a single test that restarts the sidecar. Two options:

**Option A — explicit (tests opt in):** leave the fixture alone; have
the three lifecycle tests call `http.rediscover(app_state.sidecar_pid())`
explicitly after `app_state.wait_launched()`. Keeps the fixture simple;
keeps the rediscover contract visible in the test body.

**Option B — implicit via app_state hook:** add an `on_relaunched`
callback list to `AppState` that the `http` fixture subscribes to with
a closure that calls `client.rediscover(...)`. Cleaner for authors but
adds coupling between `app_state` and the `http` driver that doesn't
exist today.

Recommend Option A — it's the minimum change, matches the explicit
comments already in the test files, and avoids cross-driver coupling.

### 4. Update lifecycle tests

- `test_session_persistence.py`: after L34 `app_state.wait_launched()`,
  add `http.rediscover(app_state.sidecar_pid())`.
- `test_sidecar_respawn.py`: replace the L45–55 `http.health()` retry
  loop with `http.rediscover(new_pid)` followed by a single
  `post = http.health()` assertion.
- `test_session_list_persistence.py`: after fixing the TypeError on L14,
  add `http.rediscover(app_state.sidecar_pid())` between `app_state.launch()`
  (L15) and the next `http.sessions()` call (L17). Note this file also
  doesn't call `wait_launched()` after `launch()` — recommend adding it
  so the sidecar is ready before the rediscover call.

## Confidence

**High** that the TypeError on `wait_quit(timeout=15)` is the proximate
cause of all three failures currently in the runs — this is a literal
signature mismatch visible in the XML stack traces, and the cascade
pattern perfectly matches a session-scoped fixture that got into a
half-quit state.

**High** that the rediscover gap is real but currently masked — the test
file comments explicitly flag it and the driver confirms `HTTPClient` has
no `rediscover()` method. Once the TypeError is fixed we should expect
at least one of the remaining two tests to newly surface this gap.

**Moderate** on the lifecycle-2 "`open -a` produces no pid" secondary
cascade — it could be Launch Services state from the unclean prior run,
or it could be an unrelated flake in GPD's startup. Re-running after
fixing #1 is the cheapest way to disambiguate.
