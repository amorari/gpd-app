# Annoying Things — subtle bugs, their causes, and the fixes that stuck

Running log of bugs that were non-obvious at first glance. Entries lead with the symptom, explain the root cause, and record the fix that shipped — so future debugging sessions don't rediscover the same coherence issues from scratch.

---

## 2026-04-23 — "Change API key" flashes welcome screen then snaps back to main IDE

### Symptom

User clicks **Change API key** (sidebar, settings panel, command palette, or Revoke Consent in settings). The welcome/entry page appears for ~500 ms, then the app jumps back to the main IDE as if no reset happened. Disk state IS actually reset (`~/.local/share/opencode/auth.json` is emptied by the Tauri `remove_gpd_key` command), but the UI refuses to stay on the entry page.

### Root cause

Cross-process cache-coherence race between the frontend and the opencode sidecar:

1. Reset handler writes `auth.json` with the `gpd` entry removed — synchronous FS write, completes immediately.
2. Handler calls `void globalSDK.client.global.dispose()` — **fire-and-forget, not awaited** (intentional: `settings-general.tsx` comment documents past sidecar hangs when awaited).
3. Handler clears `localStorage["gpd.key.saved"]` and calls `window.location.reload()`.
4. Post-reload, the sidecar's in-memory `provider.connected` cache still reports `["gpd"]` for one refresh tick because `InstanceState.make`'s `ScopedCache` (`packages/opencode/src/effect/instance-state.ts`) is only invalidated by the dispose call that hasn't finished yet.
5. Effect `eff363` at `packages/app/src/app.tsx:363` sees `gpdAuthed=true` (stale) and `hasKey()=false` (fresh), promotes `hasKey=true`, writes `gpd.key.saved=true` back to localStorage, and the app routes back to the main IDE.

Existing comment at `packages/app/src/components/settings-general.tsx:548-550` acknowledged this race but didn't fix it.

### Why the obvious fixes are wrong

- **Await the dispose:** reintroduces the sidecar-hang coupling the Tauri FS command was specifically built to avoid.
- **Make the sidecar `/provider` re-read `auth.json` on every call:** breaks `InstanceState` + `ScopedCache` architecture that's shared with 5+ upstream subsystems (skills, snapshot, pty, file/watcher, file/index). Divergence from upstream is permanent rebase cost.
- **Cross-check `auth.json` inside `eff363` via `createResource`:** `createResource` is one-shot on mount — if `auth.json` is written post-mount (first-launch installer path), the resource caches `null` and `eff363` refuses to promote the legitimate key → regression.
- **Eliminate the reload entirely (signal-flip only):** architecturally cleanest (reset = inverse of `handleApiKeySaved`), but large blast radius across 4 reset sites + reintroduces sidecar-liveness coupling via the required `globalSync.bootstrap()` await. Deferred to a future refactor.

### Fix that shipped

**Sentinel-flag pre-latch.** Every reset handler writes `localStorage["gpd.key.resetting"]="1"` immediately before the reload. `app.tsx` reads and clears that sentinel at mount, using it to seed `reonboardLatched=true` — which is the existing latch that `eff363` already early-returns on (its original purpose was closing a different ping-pong race).

Flow post-fix:

1. Reset handler: FS write → void dispose → clear `gpd.key.saved` → **set `gpd.key.resetting=1`** → reload.
2. Post-reload mount: read sentinel → clear sentinel → `reonboardLatched=true` → `eff363` early-returns → stale `provider.connected=["gpd"]` is ignored.
3. Sidecar catches up (dispose finishes or next instance request rebuilds state) → `provider.connected=[]` → `eff448` demotes (noop since `hasKey` already false) → welcome screen stays put.

### Files touched

- `packages/app/src/app.tsx` — sentinel read + `reonboardLatched` seed
- `packages/app/src/pages/layout.tsx` — 2 reset sites (sidebar, command palette)
- `packages/app/src/components/settings-general.tsx` — 2 reset sites (Change API key, Revoke Consent)

### Known constraint going forward

Any **new** reset-and-reload path must also write the sentinel. The "eliminate the reload" refactor (mirror `handleApiKeySaved`'s signal-flip pattern) would remove this discipline requirement — tracked as a future improvement but not blocking.

### Evidence artifacts

Three parallel review agents evaluated four fix candidates (sentinel / auth.json cross-check / sidecar freshness / no-reload). Verdict 2–1 for the sentinel approach; dissent favored the no-reload refactor as structurally cleaner but larger-scope. See session transcript 2026-04-22 / 2026-04-23.
