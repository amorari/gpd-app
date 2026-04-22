# Sidecar Supervisor Architecture (Decision 0.C)

**Status:** DRAFT — default pick. User veto window open until Task 1.5 implementation starts.
**Decided:** 2026-04-22
**Decided by:** claude
**Supersedes:** PR #15 entirely

---

## Problem

Today's sidecar lifecycle on `gpd` HEAD (verified 2026-04-22):

| Piece | Where | Role |
|---|---|---|
| `ServerState { child: Arc<Mutex<Option<CommandChild>>> }` | `lib.rs:70` | Holds the spawn handle. |
| `SidecarReady(Shared<oneshot::Receiver<ServerReadyData>>)` | `lib.rs:75` | One-shot "here are the creds" channel, consumed once by frontend. |
| `initialize(app)` task | `lib.rs:564` | Runs first-time setup + spawn_local_server + sends SidecarReady. |
| `kill_sidecar` Tauri command | `lib.rs:79` | Takes the child, calls `.kill()`. |
| `CommandChild { kill: mpsc::Sender<()> }` | `cli.rs:74` | Internal: sends `()` to the spawn task which does `child.start_kill()`. |
| Health check | `lib.rs:697` (spawned during init, 30s timeout) | Best-effort startup probe. |

**No watchdog currently exists on `gpd`.** PR #15 wants to add one by attaching a poll loop to the same `Arc<Mutex<Option<CommandChild>>>` + a new `AtomicBool` for "stopping" + generating fresh port/password on respawn. Five races / incorrectnesses result (documented in `docs/PR-REVIEW-2026-04-22.md` § PR #15):

1. Respawn issues fresh port/password, but `SidecarReady` oneshot is consumed — frontend keeps stale creds → dead connection.
2. Shutdown race: `kill_sidecar` can `take()` the child between watchdog `check stopping` and `check child` → watchdog sees `None`, respawns orphan during app exit.
3. No backoff / no retry budget → fork-bomb on crash-at-startup.
4. SIGKILL-only on exit → up to 1s of gpd-logger events lost (logger debounces at `packages/opencode/src/sink/gpd-logger.ts:169-175`).
5. Health check after respawn is bound to `_hc` and dropped — no liveness observation post-respawn.

The root cause is that lifecycle state is scattered across primitives that cannot be safely coordinated by pair-wise locking.

## Goals

1. One place owns the `CommandChild`, the current `ServerReadyData`, and the lifecycle state transitions.
2. Credentials that change on respawn reach the frontend automatically.
3. Crash-loop is bounded (exponential backoff, retry budget, fatal state).
4. Graceful shutdown gives gpd-logger time to drain pending events before SIGKILL.
5. Tests: lifecycle transitions can be exercised without spawning real processes (via an injected spawner).

## Design

### Supervisor task

One long-running `tokio::spawn`ed task per app session:

```rust
// packages/desktop/src-tauri/src/supervisor.rs (new)

pub enum SidecarState {
    Spawning,
    Ready(ServerReadyData),
    Degraded { reason: String, retry_at: Instant, attempt: u32 },
    Fatal(String),
}

enum SupervisorCmd {
    // External → supervisor:
    Shutdown(oneshot::Sender<()>),
    // Internal (supervisor → itself):
    ChildExited { exit_code: Option<i32> },
}

pub struct SupervisorHandle {
    cmd_tx: mpsc::Sender<SupervisorCmd>,
    state_rx: watch::Receiver<SidecarState>,
    join: Option<JoinHandle<()>>,
}
```

The supervisor owns:

- `child: Option<CommandChild>` — currently spawned process, if any.
- `current_ready: Option<ServerReadyData>` — last emitted creds.
- `attempt: u32` — respawn count in the current failure window.
- `window_start: Instant` — when the current failure window began.

The supervisor responds to:

- A `ChildExited` event (observed by spawning a `child.wait()` sidecar task).
- A `Shutdown` command from `kill_sidecar` or from the Tauri app lifecycle hook.
- No polling loop. State changes are event-driven.

### State transitions

```
                spawn() attempt
   [Spawning] ──────────────────► [Ready(creds)]
       │                               │
       │ spawn failure                 │ ChildExited
       │                               │
       ▼                               ▼
 [Degraded] ──► backoff + retry ──► [Spawning]
       │
       │ attempts > budget
       ▼
   [Fatal]
```

- `Ready` → `Ready(new_creds)` on respawn: broadcast new `ServerReadyData` via `state_rx`.
- `Degraded` holds `retry_at` so the UI can render a countdown.
- `Fatal` terminates the task; user must quit + relaunch.

### Backoff policy

- Base: 1s, 2x each failure, cap 60s.
- Window: 5 failures in 60s → `Fatal`.
- Window resets on 60s of continuous `Ready`.
- Jitter: +/- 20% to avoid thundering herds with the OS scheduler.

### Credential broadcast to frontend

Replace `SidecarReady(Shared<oneshot::Receiver>)` with a `watch::Receiver<SidecarState>` exposed as Tauri state. Frontend at `packages/desktop/src/index.tsx:469` subscribes via:

```ts
// Tauri event-based, not the old one-shot
const unlisten = await appWindow.listen<SidecarStateEvent>("sidecar-state", (e) => {
  if (e.payload.kind === "ready") {
    // Rebind ServerConnection to new port/password.
  } else if (e.payload.kind === "degraded") {
    // Show reconnecting banner.
  } else if (e.payload.kind === "fatal") {
    // Show "sidecar failed, restart app" dialog.
  }
})
```

Rust emits the event via `app.emit("sidecar-state", ...)` whenever `state_rx` changes.

### Graceful shutdown

`kill_sidecar` becomes a Tauri command that forwards to `SupervisorCmd::Shutdown(ack_tx)` and awaits `ack_rx`:

```
1. Supervisor sees Shutdown cmd.
2. Sends SIGTERM (or an IPC shutdown command — see below) to the child.
3. Waits up to GPD_SHUTDOWN_DEADLINE_MS (default 3000) for child.wait().
4. On deadline miss: SIGKILL, log warn.
5. Supervisor transitions to a terminal "shutting down" state.
6. ACK the shutdown via ack_tx.
7. Caller awaits ack before returning to Tauri runtime.
```

### gpd-logger shutdown contract

SIGTERM alone doesn't fix the flush-loss window — the sidecar needs a signal handler that synchronously drains pending log events before exit.

**Sidecar side (`packages/opencode/src/`):**

- Install SIGTERM (Unix) / Windows equivalent handler early in sidecar startup. On receipt:
  1. Drop new incoming Bus events (close the subscription).
  2. Force-flush the `GpdLogger` pending queue via a single blocking HTTP POST to `/gpd/log`.
  3. `process.exit(0)`.
- Add a `Scope` finalizer to `GpdLogger.Service` at `packages/opencode/src/sink/gpd-logger.ts` that runs the flush on normal scope close (covers non-SIGTERM exits too).
- Flush timeout budget: 1500ms. If HTTP flush doesn't complete, give up and exit anyway — don't block SIGKILL indefinitely.

**Rust side:**

- `GPD_SHUTDOWN_DEADLINE_MS` default 3000 gives 1500ms for flush + 1500ms slack.
- On macOS/Linux: `unsafe { libc::kill(pid, libc::SIGTERM) }` (NOT `child.start_kill()` which is SIGKILL on tokio 1.x).
- On Windows: use `CtrlCEvent` sent to the child process group, or a dedicated shutdown IPC channel.
- After deadline: `child.start_kill()` (SIGKILL).

This contract is load-bearing for Decision 0.C. Without it, the SIGTERM is cosmetic and we still lose 1 second of logs on every clean quit.

### Testability

Supervisor takes a `Spawner` trait:

```rust
trait Spawner: Send + Sync {
    fn spawn(&self) -> BoxFuture<'static, io::Result<(CommandChild, ServerReadyData, CommandEventStream)>>;
}
```

- Production: `SidecarSpawner` that calls the existing `server::spawn_local_server`.
- Tests: `MockSpawner` with scripted successes/failures that exercises the state machine without touching a real process.

Three unit tests land with Task 1.5:

1. Happy-path respawn: mock spawner returns ok twice; after first `ChildExited`, state reaches `Ready(new_creds)` with distinct `ServerReadyData`.
2. Crash loop → Fatal: mock spawner fails 5 times within 60s window; state reaches `Fatal`.
3. Clean shutdown during `Spawning`: shutdown cmd during a pending spawn doesn't leave an orphan.

### Race guarantees

The previous architecture had a lifecycle-state race because two separate primitives had to be checked in sequence. The supervisor task model replaces this with a single-threaded state-machine: all state transitions happen inside one `tokio::select!` block. No two observers need to agree on the state; there is one state, authoritatively held by the task.

`kill_sidecar` no longer takes the child directly. It sends `Shutdown` and awaits the ACK. If the supervisor is currently spawning, the command is handled in the same `select!` and the spawn is cancelled cleanly.

## Options considered

### Option A — keep the current "no watchdog, one-shot ready" model and accept PR #15 as a stop-loss

Rejected. PR #15 would regress more than it improves (see Findings 1–5 above).

### Option B — refactor to the supervisor model (THIS DECISION)

Selected. Higher up-front cost, permanent correctness.

### Option C — external supervisor (systemd-style launchd agent for macOS)

Rejected. Out of scope for the Tauri bundle model. Adds platform-specific plumbing for no real benefit over an in-process supervisor for this single-child case.

## Scope

Lands as Task 1.5 with the following file set:

- NEW `packages/desktop/src-tauri/src/supervisor.rs` — supervisor task + `Spawner` trait + `SidecarState` enum + `SupervisorHandle`.
- MOD `packages/desktop/src-tauri/src/lib.rs`:
  - Replace `ServerState` / `SidecarReady` with the `SupervisorHandle` Tauri-managed state.
  - `kill_sidecar` → `Shutdown` command + ACK.
  - `initialize()` sets up the supervisor + wires the `Spawner`.
- MOD `packages/desktop/src-tauri/src/cli.rs`:
  - Expose the spawn primitives as a `Spawner` impl.
- MOD `packages/desktop/src-tauri/src/server.rs`:
  - Ensure the health-check future is awaited or surfaced as a transition signal, not bound to `_hc`.
- MOD `packages/opencode/src/sink/gpd-logger.ts`:
  - Add SIGTERM handler + Scope finalizer that synchronously drains pending events.
  - Bounded 1500ms flush budget.
- MOD `packages/desktop/src/index.tsx`:
  - Replace one-shot resource with `listen("sidecar-state")` subscriber that rebinds `ServerConnection` on `Ready` events.

Out of scope:

- IPC shutdown channel (future improvement — SIGTERM + flush handler is sufficient for now).
- Cross-sidecar coordination (only one sidecar per app).
- Persistent state across app restarts (every launch starts fresh).

## Acceptance tests

1. Kill the sidecar via Activity Monitor → UI transitions to "reconnecting" within 2s → reconnects without user action.
2. Kill the sidecar in a tight loop (script: `while true; do pkill -9 opencode-cli; sleep 2; done`) → UI reaches "sidecar failed, please restart" after 5 attempts.
3. Quit the app with an active session emitting events → BigQuery shows every pre-quit event within 30s (proves flush drained).
4. Tauri MCP test: assert no orphan `opencode-cli` processes after app exit.

## Veto

Revert this commit + the Task 1.5 implementation if:
- The `SidecarState` enum shape is wrong (e.g., needs a richer degraded reason taxonomy).
- SIGTERM-based flush is infeasible on Windows and we need to swap in an IPC shutdown channel.
- The supervisor-task concurrency model conflicts with an ongoing Tauri upgrade.

Acceptable counter-proposal: keep a similar state-machine but use an async `futures::channel::mpsc::UnboundedSender` for commands and a dedicated shutdown IPC to the sidecar instead of signals. Document the rationale.
