# GPD session logging

**Audience:** future engineers / agents making changes here. This doc is the
single source of truth for *why* the logging stack looks the way it does and
*where* to poke at it. Operational setup commands live in
`infra/litellm/README.md`, `infra/bigquery/README.md`, and the scripts under
`scripts/`.

---

## TL;DR

Every GPD Desktop session is streamed, as it happens, to
`gs://gpd-desktop-logs`, then rolled up into BigQuery. Desktop clients
authenticate with their existing LiteLLM virtual key — **no GCS credentials
ship with the app.** The SA key that writes to the bucket lives only on
Railway next to LiteLLM.

```
OpenCode session (SQLite, per-part, already exists)
        │
        │ Bus events: Session.Updated, MessageV2.Updated, PartUpdated,
        │              Session.Diff, Session.Deleted
        ▼
packages/opencode/src/sink/gpd-logger.ts        (bus sink, mirrors ShareNext)
        │
        │ 1 s debounced flush, per-session coalesce,
        │ gzip NDJSON body, atomic disk spill on failure
        ▼
POST https://litellm-production-46bb.up.railway.app/gpd/log
  Authorization: Bearer <user's LiteLLM virtual key>
  Content-Encoding: gzip
  ?session=<id>&root_session=<id>&seq=<ULID>
        │
        ▼
LiteLLM proxy on Railway (stock image + LITELLM_WORKER_STARTUP_HOOKS)
  1. Content-Length ≤ 64 MB gate
  2. Depends(user_api_key_auth)   — validates key, handles revocation/expiry
  3. proxy_logging_obj.pre_call_hook — reuses RPM/TPM limiter
  4. Redis per-key daily byte quota (fail-closed)
  5. user_hash = sha256(user_api_key_dict.user_id)[:16]  (server-derived)
  6. Idempotent GCS upload (if_generation_match=0)
        │
        ▼
gs://gpd-desktop-logs/
  user=<hash>/date=YYYY-MM-DD/session=<root>/
    parts/<ULID>.jsonl.gz                         (one object per flush)
    subagents/agent-<child>/parts/<ULID>.jsonl.gz (flat, not nested by depth)
        │
        ▼
BigQuery gpd_logs.sessions_external (Hive-partitioned on user, date)
        │
        │ 6h scheduled transfer (today only) — 03-materialize.sql
        ▼
BigQuery gpd_logs.sessions (partition ingest_date, cluster user_hash+session_id)
  + sessions_text_index SEARCH index on string cols
```

---

## Why we're here

Physics researchers using GPD Desktop generate long, subagent-heavy research
sessions (confirmed: one Claude Code session with **2,671 subagents / 2.5 GB**
on disk). PSI needs every session persisted to GCS for:

1. **Ops / debug** — "Prof X says the derivation at time T was wrong; show me
   the transcript."
2. **Billing reconciliation** — match LiteLLM spend vs. upstream
   Anthropic/OpenAI/Google invoices.
3. **Abuse detection** — "Which virtual keys are burning spend, and on what?"
4. **Compliance** — per-user GDPR deletion, retention policies.
5. **Fine-tuning / research output** — extract aggregate stats, curate Q&A
   datasets.

The design goals that fell out:

- **O(N) storage** per session — no O(N²) repetition of system prompt / tool
  catalog per turn.
- **Subagent-tree correlation** — every subagent's logs traceable to the
  same root session.
- **Zero user-visible latency** — logging is off the chat critical path; if
  GCS is down the session still works, flushes spill to disk.
- **SQL analytics via BigQuery** — cheap at our scale, zero extra ops surface.
- **Per-user GDPR deletion** — user-partitioned path prefix makes `rm -r` by
  user_hash a one-liner.

---

## Decisions (and what we rejected)

### Don't bake the GCS SA key into the Tauri bundle
Initial plan was `include_str!("gpd-log-writer-key.json")` in `lib.rs`. That
means anyone who unpacks the `.app` gets `storage.objectCreator` on
`gs://gpd-desktop-logs`. Scoped no-read / no-list / no-delete, but still
lets an attacker:
- Write arbitrary garbage (pollutes BigQuery, DoS storage $)
- Spam 10 GB/day of junk (denial-of-wallet)
- Impersonate other users by writing under `user=<otherHash>/`

"Only objectCreator" does not mitigate any of those. The cost of switching
to Option A (route through LiteLLM) is small; the security story is much
cleaner.

### Route logs through LiteLLM (Option A), not a dedicated Cloud Run sidecar
Considered four architectures (labeled A–D in the original plan):

- **A — Log through LiteLLM** (picked)
- B — Dedicated Cloud Run log-ingest service that validates the key against
  LiteLLM's `/key/info`
- C — LiteLLM-side `CustomLogger` only (skips the OpenCode-side richness —
  loses ~40% of what we capture today)
- D — GCS signed URLs minted per-flush by LiteLLM (extra RTT per flush)

A won because: the client already holds a LiteLLM virtual key, the auth
path is already battle-tested for every LLM call, and LiteLLM already
knows how to talk to GCS (it ships a `gcs_bucket` callback internally).
Minimal new ops surface.

### Tiny Dockerfile fork, not start-command `curl` loader
Considered having LiteLLM `curl` the hook module from a config GCS bucket
at boot (zero Dockerfile fork), but that couples container startup to
config-bucket reachability. The trivial 3-line `FROM` + `COPY` Dockerfile
is simpler to reason about. Railway's `railway up` from `infra/litellm/`
rebuilds the image; the `FROM ...:main-stable` rolling tag picks up
upstream LiteLLM updates each redeploy.

### One object per flush, not one per session
GCS has a 1-write/sec-per-object ceiling. During subagent fan-out (10
subagents flushing at 1 s cadence) we'd blow through that if everyone
wrote to the same `root.jsonl.gz`. Instead each flush gets its own
`parts/<ULID>.jsonl.gz`. A nightly compactor (see "Compactor" below) fuses
them via `Objects.compose()` into a single `root.jsonl.gz` per session
per day.

**ULID naming, not sequential integers.** ULIDs sort lexicographically ==
chronologically, are unique across client restarts without any shared
counter, and let us go straight to GCS without a distributed sequence
service.

### OpenAI `metadata` field for session-id correlation, not custom headers
Phase 1 threads `gpd_session_id` / `gpd_parent_session_id` /
`gpd_root_session_id` / `gpd_agent` into the OpenAI-compatible request
body's `metadata` field on every LLM call. LiteLLM auto-records these
into `proxy_server_request.metadata.*` in its spend logs, so a BigQuery
join between spend_logs and `gpd_logs.sessions` on `gpd_root_session_id`
lets us answer "what did subagent X cost on this session?" without
needing custom LiteLLM surgery.

Verified empirically against `/spend/logs/ui?request_id=<id>`.
`@ai-sdk/openai-compatible` spreads any unknown key in
`providerOptions[providerID]` onto the top-level request body, so
`providerOptions.gpd.metadata = {...}` lands as `body.metadata = {...}`.

### Whitelist `/gpd/log` as an LLM route on LiteLLM
`RouteChecks.non_proxy_admin_allowed_routes_check` rejects any route not
in `openai_routes / anthropic_routes / google_routes / mcp_routes / etc.`
for non-admin virtual keys. Our hook monkey-patches
`LiteLLMRoutes.openai_routes.value.append("/gpd/log")` so virtual keys
pass the check. We intentionally do NOT set `cost_per_request` on the
route, so log writes don't charge against the user's LLM budget.

### Today-only materialize, every 6h
Original plan had yesterday + today scans every hour. With no real users
yet there's no midnight-spanning-session problem to solve, and every
additional hour of lookback 2× the scanned bytes (BigQuery bills on
uncompressed). We picked:
- **Every 6h** — max 6h lag before a session shows up in the clustered
  table. Fine for ops/debug.
- **Today only** — 4× fewer bytes scanned per run. Comments in
  `03-materialize.sql` point to the two windows to widen once sessions
  actually span midnight.

### Content-hash dedup (Phase 5) — DEFERRED
The 45× storage reduction Agent 1 projected was calculated against Claude
Code's JSONL shape, which writes the full `proxy_server_request` body
(system prompt + all tool schemas) every turn. **Our Bus-event capture
doesn't include those at all.** `MessageV2.Event.Updated` and
`PartUpdated` carry message/part state only, not the assembled LLM
request. So the O(N²) growth that dedup was meant to eliminate doesn't
exist in our schema; dedup would at best save a few percent.

Reactivate Phase 5 if we add a parallel LiteLLM callback that logs
assembled request bodies (see "Future work" below).

### Admin viewer (Phase 6) — DEFERRED
BigQuery Studio + `gcloud storage cat` is enough for engineers. Revisit
when a non-engineer needs self-serve audit.

---

## What's where

### Client side (TypeScript, ships in the sidecar)

| File | What it does |
|---|---|
| `packages/opencode/src/sink/schema.ts` | `GpdLog.Event` union — one type per logged event kind (`session_init`, `message_updated`, `part_updated`, `session_diff`, `session_deleted`, `session_close`) |
| `packages/opencode/src/sink/gpd-logger.ts` | The Service. Mirrors `share-next.ts`: subscribes to 5 Bus events, coalesces updates per-session-per-key inside a 1 s flush window, materializes events, calls `GpdLogHttp.post`. Memoises `Session.root()` per session. Spawns the boot replay + retry loop. Gated on `OPENCODE_GPD_LOGS_ENABLED=1`. |
| `packages/opencode/src/sink/http-writer.ts` | Gzip + POST through LiteLLM. Handles 401/403 (auth — stop retrying), 413 (permanent — drop), 429 (quota — back off), 5xx + network (spill for retry). ULID `seq` per flush. |
| `packages/opencode/src/sink/spill.ts` | On-disk pending queue at `~/.local/share/opencode/gpd-log-spill/`. `<ulid>.gz` + `<ulid>.meta`, tmp + fsync + rename + fsync-dir for crash safety, FIFO drop at 1 GiB. |
| `packages/opencode/src/sink/jsonl-writer.ts` | Optional local-FS mirror, activated by `OPENCODE_GPD_LOG_LOCAL_MIRROR=1`. Writes structured JSONL under `~/.local/share/opencode/gpd-session-logs/<rootSessionID>/` for dev debuggability. Off by default in production; the spill dir above is the only local-disk artifact. |
| `packages/opencode/src/session/llm.ts` | Phase 1: injects GPD metadata into the LLM call when the provider is LiteLLM-bound (includes our `gpd` provider). |
| `packages/opencode/src/session/index.ts` | `Session.root(id)` helper — walks the `parent_id` chain, bounded at 100 hops. |
| `packages/opencode/src/session/prompt.ts`, `compaction.ts` | Callers compute `rootSessionID` via `Session.root()` and pass it through `StreamInput`. Title-gen doesn't need it (runs only on root sessions). |
| `packages/opencode/src/effect/{bootstrap,app}-runtime.ts`, `packages/opencode/src/project/bootstrap.ts` | Register `GpdLogger.Service` alongside `ShareNext.Service`. |
| `packages/desktop/src-tauri/src/lib.rs` | Sets `OPENCODE_GPD_LOGS_ENABLED=1` on sidecar spawn so release builds log out of the box. Also the Phase-0 `OPENCODE_DISABLE_SHARE=1`. |
| `packages/opencode/test/sink/*.test.ts` | Bun tests for spill atomicity + JSONL writer subagent routing + tool-output spill. |

### Server side (Python, shipped via `infra/litellm/`)

| File | What it does |
|---|---|
| `infra/litellm/Dockerfile` | 3-line layer on top of `ghcr.io/berriai/litellm:main-stable`. Adds `gpd_log/` to `/app/` and sets `LITELLM_WORKER_STARTUP_HOOKS=gpd_log.hook:register`. |
| `infra/litellm/railway.json` | Forces Railway's builder to `DOCKERFILE` mode (otherwise Railpack auto-detect finds `bun.lock` and tries to build the whole monorepo). |
| `infra/litellm/gpd_log/hook.py` | The `register()` entry. Appends `/gpd/log` to `LiteLLMRoutes.openai_routes.value` and calls `app.add_api_route(...)`. Runs inside FastAPI lifespan startup. |
| `infra/litellm/gpd_log/handler.py` | The route itself. Content-Length gate → `Depends(user_api_key_auth)` → `pre_call_hook` → Redis byte quota → server-derived `user_hash` → GCS upload. |
| `infra/litellm/gpd_log/quota.py` | Per-hashed-token daily byte counter in Redis. Fail-closed on Redis outage. Default cap 1 GiB/day (override via `GPD_LOG_BYTES_PER_DAY`). |
| `infra/litellm/gpd_log/gcs_writer.py` | `upload_from_string(if_generation_match=0)` — idempotent. Treats 412 as success so client-side spill retries don't duplicate data. |
| `infra/litellm/gpd_log/compactor.py` | Nightly fuser: `parts/*.jsonl.gz` → `root.jsonl.gz` via `Objects.compose()` (32-at-a-time, two-phase for >32 parts). Run as `python -m gpd_log.compactor --yesterday`. Not currently scheduled — the nightly job is TODO. |

### Analytics (BigQuery)

| File | What it does |
|---|---|
| `infra/bigquery/01-external-table.sql` | Creates `gpd_logs.sessions_external` over the whole bucket, Hive-partitioned on `user` + `date`, `require_hive_partition_filter=true` to prevent accidental full-bucket scans. |
| `infra/bigquery/02-materialized-sessions.sql` | Creates `gpd_logs.sessions` — partition by `ingest_date`, cluster by `(user_hash, session_id)`. |
| `infra/bigquery/03-materialize.sql` | Scheduled INSERT. Today-only window, anti-dedupe via `source_object NOT IN (...)` against today's materialized rows. |
| `infra/bigquery/README.md` | Step-by-step setup commands, example queries, cost-tuning knobs. |

### GDPR + retention

| File | What it does |
|---|---|
| `infra/gcs/lifecycle.json` | 30 d → NEARLINE, 90 d → COLDLINE, 365 d → ARCHIVE, 730 d → Delete. Applied live to `gs://gpd-desktop-logs`. |
| `scripts/delete-user.ts` | `bun scripts/delete-user.ts --user-id=<id> [--confirm]`. Purges GCS prefix, BQ rows, and LiteLLM virtual keys. Dry-run by default. |

---

## Current deployed state (as of 2026-04-21)

### GCP project `gpd-desktop`
- Bucket `gs://gpd-desktop-logs` — `US-CENTRAL1`, lifecycle applied, soft-delete disabled
- Service account `gpd-log-writer@gpd-desktop.iam.gserviceaccount.com` — `roles/storage.objectCreator` only, no read/list/delete
- Project-level org policy override on `constraints/iam.disableServiceAccountKeyCreation` = `enforce: false` (org default is `enforce: true`)
- SA key exists only as the `GOOGLE_APPLICATION_CREDENTIALS_JSON` env var on Railway's `litellm` service

### Railway project `psi-gpd`
- Service `litellm`, production environment
- Source: this repo, `infra/litellm/` as build root (Dockerfile mode via `railway.json`)
- Public URL: `https://litellm-production-46bb.up.railway.app`
- Env vars added for logging:
  - `GOOGLE_APPLICATION_CREDENTIALS_JSON` — inline SA JSON
  - `GPD_LOG_BUCKET=gpd-desktop-logs`
  - `GPD_LOG_BYTES_PER_DAY` — unset, defaults to 1 GiB/day/key
  - `LITELLM_WORKER_STARTUP_HOOKS` — baked into Dockerfile, **do not** also set in Railway env (would double-register)
- Redeploys: push changes to the `gpd` branch that touch `infra/litellm/`, then `railway up infra/litellm --path-as-root --service litellm --detach`, OR click Redeploy in the Railway dashboard

### BigQuery project `gpd-desktop`, dataset `gpd_logs`
- `sessions_external` — external table over `gs://gpd-desktop-logs/*`
- `sessions` — native clustered table, 730-day partition expiration
- `sessions_text_index` — SEARCH index on string cols
- Scheduled transfer config `6a32e0bb-0000-2128-9732-94eb2c1f907c` — "gpd_logs 6h materialize (today only)", runs every 6h, state `RUNNING`

---

## Data model

### What's on the wire

Each `/gpd/log` POST body is a gzipped NDJSON stream of `GpdLog.Event`s. The
union:

```ts
type Event =
  | SessionInitEvent        // kind: "session_init"
  | MessageUpdatedEvent     // kind: "message_updated"
  | PartUpdatedEvent        // kind: "part_updated"
  | SessionDiffEvent        // kind: "session_diff"
  | SessionDeletedEvent     // kind: "session_deleted"
  | SessionCloseEvent       // kind: "session_close"
```

All events carry `ts` (ms epoch), `v` (schema version, currently 1), and
`sessionID`. `session_init` is the one event that includes
`parentSessionID` + `rootSessionID` inline; for all other events the root is
derived from the `session=<root>/` path segment at materialize time.

### What's in GCS

```
gs://gpd-desktop-logs/
  user=<sha256(user_id)[:16]>/
    date=YYYY-MM-DD/
      session=<rootSessionID>/
        parts/<ULID>.jsonl.gz
        subagents/agent-<childSessionID>/parts/<ULID>.jsonl.gz
        root.jsonl.gz           ← written by the nightly compactor
```

`user_hash` is **server-derived** from `user_api_key_dict.user_id`. The
client cannot steer which prefix it writes under. Tool outputs >32 KB
are NOT currently spilled to side files on the HTTP path — only the
(deprecated, opt-in) local-FS mirror does that.

### What's in BigQuery

`sessions_external`: one row per NDJSON line, Hive columns (`user`, `date`)
auto-added by BigQuery.

`sessions`: same rows, but with:
- `ingest_date` promoted from path (DATE) — partition key
- `user_hash` promoted from path (STRING) — cluster key
- `session_id`, `root_session_id` regex-extracted from `_FILE_NAME` when
  absent from the payload (`REGEXP_EXTRACT(_FILE_NAME, r'/session=([^/]+)/')`)
- `source_object` — full `gs://...` URI, enables anti-dedupe and easy
  "go fetch the raw file" debugging
- `ingested_at` — materialize-run timestamp

---

## Deploying changes

### Client-side change (TypeScript)
1. Edit under `packages/opencode/src/sink/` or `packages/opencode/src/session/`.
2. `bun turbo typecheck --filter=opencode` + run bun tests if touching
   `spill.ts` / `jsonl-writer.ts`.
3. Commit to `gpd` branch; CI rebuilds the sidecar; next release ships.

### Server-side change (Python)
1. Edit under `infra/litellm/gpd_log/`.
2. Syntax check: `python3 -c 'import ast; ast.parse(open("infra/litellm/gpd_log/<file>.py").read())'`.
3. Commit to `gpd` branch.
4. Deploy: `railway up infra/litellm --path-as-root --service litellm --detach`
   (wait ~30–60s for build; LiteLLM has a brief restart during rollover).
5. Smoke test the changed path — the curl snippet in `infra/litellm/README.md`
   is reusable.

### BigQuery SQL change
1. Edit `infra/bigquery/*.sql`.
2. Dry run: `bq query --dry_run --use_legacy_sql=false --parameter='run_date:DATE:2026-04-21' < infra/bigquery/03-materialize.sql`.
3. If it's a scheduled-query change, re-create the transfer config:
   ```bash
   bq rm -f --transfer_config --project_id=gpd-desktop <OLD_ID>
   QUERY=$(cat infra/bigquery/03-materialize.sql)
   bq mk --transfer_config --data_source=scheduled_query --target_dataset=gpd_logs \
     --project_id=gpd-desktop --location=US \
     --display_name="gpd_logs 6h materialize (today only)" \
     --schedule="every 6 hours" \
     --params="$(jq -n --arg q "$QUERY" '{query: $q}')"
   ```
4. Commit.

### Adding a new LiteLLM env var
Use `railway variables --set KEY=VALUE --service litellm`. That triggers
a redeploy automatically.

---

## Operating

### Where to look when something's broken

| Symptom | First place to look |
|---|---|
| Client showing "logging disabled" or toasts about auth | `Auth.Service.get("gpd")` state. Virtual key may have been revoked. |
| Spill dir filling up | Network or LiteLLM down. `ls ~/.local/share/opencode/gpd-log-spill/`. Fixes itself when connectivity returns; replay loop ticks every 30 s while spill is non-empty. |
| No objects in GCS | `railway logs --service litellm -d <deployment-id>` — look for Python exceptions in `gpd_log.*`. |
| BigQuery rows not appearing | Check scheduled transfer run history: `bq show --transfer_config projects/.../transferConfigs/<ID>`. |
| Slow queries | Check you're filtering on `ingest_date` + `user_hash` — cluster prune won't help without both. |

### Checking the scheduled transfer

```bash
bq ls --transfer_config --project_id=gpd-desktop --transfer_location=us
bq show --transfer_config \
  projects/310054070437/locations/us/transferConfigs/6a32e0bb-0000-2128-9732-94eb2c1f907c
# Last N runs
bq ls --transfer_run \
  projects/310054070437/locations/us/transferConfigs/6a32e0bb-0000-2128-9732-94eb2c1f907c
```

### Force a fresh materialize run

```bash
bq query --use_legacy_sql=false --project_id=gpd-desktop \
  --parameter='run_date:DATE:'$(date -u +%Y-%m-%d) \
  < infra/bigquery/03-materialize.sql
```
Idempotent; safe to run repeatedly.

### Deleting a user (GDPR)

```bash
bun scripts/delete-user.ts --user-id=<plain user id>   # dry-run by default
bun scripts/delete-user.ts --user-id=<id> --confirm \
  --litellm-master-key=$LITELLM_MASTER_KEY              # executes
```
Purges GCS prefix, BigQuery rows, and LiteLLM virtual keys for that user_id.

---

## Cost

At steady state, scales roughly linearly with active researcher count:

| Item | 1 user | 10 researchers | 100 researchers |
|---|---|---|---|
| GCS storage | <$0.01/mo | $0.50/mo | $5/mo |
| GCS writes (Class A) | <$0.01/mo | $3/mo | $30/mo |
| BigQuery storage | <$0.01/mo | $0.30/mo | $3/mo |
| BigQuery scheduled query | $0 (free tier) | $2–5/mo | $10–30/mo |
| Railway traffic | $0 (ingress free) | $0 | ~$0 |
| **Total** | **~$0/mo** | **~$5–10/mo** | **~$50/mo** |

Single biggest cost driver: the scheduled query. BigQuery bills on
uncompressed bytes processed, and our NDJSON is roughly 5-10× larger
uncompressed.

### Knobs to tune if cost matters

| Knob | Default | Effect |
|---|---|---|
| `--schedule="every 6 hours"` | 4× runs/day | Each step down halves the cost: 6h → 12h → 24h |
| Window in `03-materialize.sql` | today only | Widening to `yesterday+today` doubles bytes scanned per run |
| `partition_expiration_days=730` on `sessions` | 2 y retention | Drop to 365 if 1y audit window is acceptable |
| Lifecycle `age: 30` → NEARLINE | 30 d hot | Drop to 7 d if queries rarely hit data that old (nearline 2× cheaper) |
| `GPD_LOG_BYTES_PER_DAY` | 1 GiB/user | Tighter cap = earlier 429 for abusive clients |

---

## Limitations / known caveats

### Transfer-Encoding: chunked is not handled correctly
If a client sends the body with `Transfer-Encoding: chunked` (and no
Content-Length), Railway's edge proxy forwards the raw chunked framing,
and FastAPI/Starlette does not dechunk before we write to GCS. Result:
the stored object has chunked framing inside the gzip stream, and
BigQuery fails to read it with "unrecognized gzip format."

**In practice this never happens** — Bun's `fetch` always sends
Content-Length. The smoke test tripped this by passing the header
explicitly with `-H "Transfer-Encoding: chunked"`. Defensive rejection
in `handler.py` would close the edge case at the cost of some ceremony;
deferred until it matters.

### Content-Length gate runs inside the handler, not as middleware
Starlette freezes its middleware stack before FastAPI lifespan startup
fires, so `app.add_middleware()` in the worker-startup hook raises
`RuntimeError: Cannot add middleware after an application has started`.
We gate on Content-Length inside `gpd_log` itself; the trade-off is that
`Depends(user_api_key_auth)` runs first and already calls
`await request.body()`, which buffers up to 64 MB in RAM before our
check fires. For the current traffic shape (KB-sized debounced flushes)
this is fine. Hardening path: pre-seed `request.scope["parsed_body"]`
via a true ASGI middleware so `user_api_key_auth` skips the body drain,
then stream with `async for chunk in request.stream()`. Implement if
large upload volume ever becomes a thing.

### Per-key USD budget doesn't fire on /gpd/log
`RouteChecks.non_proxy_admin_allowed_routes_check` gates the
`_virtual_key_max_budget_check` on `is_llm_api_route(route)`. We tell
LiteLLM `/gpd/log` is an LLM route so non-admin keys can use it, but we
don't set `cost_per_request` on it, so `spend` stays 0. This is
intentional — log writes should not eat the user's LLM budget. Team/
user/org budgets still fire via `common_checks`.

### No compactor schedule yet
`infra/litellm/gpd_log/compactor.py` exists and works, but nothing calls
it on a schedule. `parts/` objects accumulate until the 730-day lifecycle
deletes them. For realistic volumes (hundreds of flushes per session-day)
this is a lot of small objects — if a given `session=<root>/` goes past
a few hundred `parts/`, querying its `subagents/*` becomes GCS-metadata-
expensive. Fix when we have enough session volume to notice. Candidates:
Railway cron `python -m gpd_log.compactor --yesterday`, Cloud Scheduler
HTTP trigger, or GitHub Actions nightly.

### Session boundaries aren't emitted
The `session_close` event type exists in the schema but the logger
doesn't currently emit it on session termination. Ending the session
just stops producing events. Low priority — you can reconstruct session
end from the `last_seen` ts of the last event on that session_id.

---

## Future work / reactivation points

- **Content-hash dedup (Phase 5)**: activate if we start logging the full
  `proxy_server_request` body (system prompt + tool schemas per turn) via
  a LiteLLM success-hook. The original Phase 5 design is preserved in
  `.claude/plans/happy-juggling-lagoon.md` for that day.
- **Admin viewer (Phase 6)**: Cloud Run + Firebase Auth restricted to
  `@psi.inc`, forking the 6 renderers under `packages/web/src/components/share/`
  plus a KaTeX renderer for physics math.
- **Bit-exact replay**: parallel LiteLLM `CustomLogger` that writes the
  exact request body (minus response body, for storage) to a 14-day sub-
  bucket, keyed on `gpd_root_session_id`. Needed only if we want to
  replay a session through a different model.
- **Scheduled compactor** (see above).
- **Streaming body ingest** (see above).
- **BigQuery Dataform / DBT layer** for per-session rollup views
  (e.g., `session_summary` — one row per session_id with turn counts,
  subagent counts, total tokens). Cheaper per-query than always
  re-aggregating from the raw event table.

---

## Escape hatches

### Disable logging on a single client
Set `OPENCODE_GPD_LOGS_ENABLED=0` (or unset it) in the client's env. The
logger service short-circuits all flushes.

### Disable server-side endpoint entirely
Remove `LITELLM_WORKER_STARTUP_HOOKS` from the Dockerfile's `ENV` line
and redeploy. Route disappears; clients start spilling locally.

### Rotate the SA key
```bash
gcloud iam service-accounts keys create /tmp/new-key.json \
  --iam-account=gpd-log-writer@gpd-desktop.iam.gserviceaccount.com \
  --project=gpd-desktop
railway variables --set "GOOGLE_APPLICATION_CREDENTIALS_JSON=$(jq -c . /tmp/new-key.json)" \
  --service litellm
shred -u /tmp/new-key.json
# Disable the old key id after Railway has picked up the new one (see dashboard)
```

### Pause the scheduled materialize
```bash
# Pause (transfer config is kept, no runs)
bq update --transfer_config \
  --disable \
  projects/310054070437/locations/us/transferConfigs/6a32e0bb-0000-2128-9732-94eb2c1f907c

# Resume
bq update --transfer_config \
  --no-disable \
  projects/310054070437/locations/us/transferConfigs/6a32e0bb-0000-2128-9732-94eb2c1f907c
```

### Purge everything (nuclear)
```bash
gcloud storage rm -r gs://gpd-desktop-logs/**
bq rm -r -f --dataset gpd-desktop:gpd_logs
```
Irreversible. Don't do this in the course of normal debugging.
