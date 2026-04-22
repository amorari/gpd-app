# GPD's LiteLLM image

Ships stock `ghcr.io/berriai/litellm:<pin>` + two custom routes:

- **`POST /gpd/log`** — session-log ingest to `gs://gpd-desktop-logs`. SA
  key lives only on Railway; desktop clients authenticate with their
  existing LiteLLM virtual key.
- **`POST /gpd/tos-accept`** — Terms-of-Service acceptance writer. Writes
  one append-only row per (user, version, device) to `gpd_tos_acceptance`
  in LiteLLM's Postgres DB. Same virtual-key auth.

## What's in here

| File | What it does |
|---|---|
| `Dockerfile` | 3-line layer on top of stock LiteLLM |
| `gpd_log/hook.py` | `register()` entry point for `LITELLM_WORKER_STARTUP_HOOKS` — wires `/gpd/log` |
| `gpd_log/middleware.py` | Rejects requests with missing / oversized Content-Length before the body hits memory |
| `gpd_log/handler.py` | The route: auth → rate-limit → byte-quota → GCS upload |
| `gpd_log/gcs_writer.py` | `upload_from_string(if_generation_match=0)` idempotent write |
| `gpd_log/quota.py` | Per-key daily byte counter in Redis, fail-closed |
| `gpd_tos/hook.py` | `register()` entry — wires `/gpd/tos-accept` |
| `gpd_tos/handler.py` | Auth → validate version → capture IP/UA → insert row |
| `gpd_tos/db.py` | Lazy `PrismaClient` singleton + parameterised `INSERT` helper |
| `scripts/create-tos-table.sql` | One-time DDL for `gpd_tos_acceptance` (apply before deploying) |

## One-time GCP setup

```bash
# SA scoped to write-only on one bucket — no list, no read, no delete.
gcloud iam service-accounts create gpd-log-writer --project=gpd-desktop \
  --display-name="GPD LiteLLM-side log writer"

gcloud storage buckets add-iam-policy-binding gs://gpd-desktop-logs \
  --member=serviceAccount:gpd-log-writer@gpd-desktop.iam.gserviceaccount.com \
  --role=roles/storage.objectCreator

gcloud iam service-accounts keys create /tmp/gpd-log-writer-key.json \
  --iam-account=gpd-log-writer@gpd-desktop.iam.gserviceaccount.com \
  --project=gpd-desktop

# Print for pasting into Railway:
cat /tmp/gpd-log-writer-key.json | jq -c .   # single-line JSON for env var
shred -u /tmp/gpd-log-writer-key.json         # destroy local copy
```

## Railway configuration

1. **Switch the LiteLLM service from "Docker image" mode to "Dockerfile" mode.**
   Settings → Source → point at this repo, root directory `infra/litellm/`.
2. **Add env vars** (Settings → Variables):
   ```
   GOOGLE_APPLICATION_CREDENTIALS_JSON = <paste SA JSON from step above>
   GPD_LOG_BUCKET = gpd-desktop-logs
   GPD_USER_HASH_PEPPER = <64 hex chars — generate once, NEVER rotate>
   GPD_LOG_BYTES_PER_DAY = 10737418240   # 10 GiB/day/key (optional; default)

   # Generate pepper:
   #   python -c 'import secrets; print(secrets.token_hex(32))'
   # Store it in Railway env only. Rotation orphans all existing GCS
   # objects (user_hash in paths uses the pepper). If you rotate, you
   # must also delete every old user=*/ prefix.
   #
   # Existing vars stay untouched: DATABASE_URL, LITELLM_MASTER_KEY,
   # REDIS_URL (or REDIS_HOST / REDIS_PASSWORD), STORE_MODEL_IN_DB, etc.
   ```
   `LITELLM_WORKER_STARTUP_HOOKS` is baked into the Dockerfile, so don't
   set it as a Railway env var (would double-register the route).
3. **Click Redeploy.** Railway rebuilds the image (~30s), the hook fires
   during worker startup, and the `/gpd/log` route becomes live.

## Verification

After deploy, with a valid LiteLLM virtual key:

```bash
KEY=sk-<your-key>
BASE=https://litellm-production-46bb.up.railway.app
SEQ=$(python -c 'import secrets, time; import string; \
  alpha="0123456789ABCDEFGHJKMNPQRSTVWXYZ"; \
  print("".join(secrets.choice(alpha) for _ in range(26)))')

# Small test body (gzipped NDJSON)
echo '{"kind":"test","ts":1}' | gzip | curl -sS -X POST \
  "$BASE/gpd/log?session=ses_test&root_session=ses_test&seq=$SEQ" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Encoding: gzip" \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @- \
  | jq

# Expected: {"ok": true, "path": "user=.../session=ses_test/parts/<SEQ>.jsonl.gz", "bytes": N}

# Check the object landed
gcloud storage cat "gs://gpd-desktop-logs/user=*/date=$(date -u +%Y-%m-%d)/session=ses_test/parts/$SEQ.jsonl.gz" \
  | gunzip
```

Negative tests:

```bash
# Missing key → 401
curl -sS -X POST "$BASE/gpd/log?session=s&seq=$SEQ" -H "Content-Length: 10" -d abc
# Revoked key → 401 (after LiteLLM cache TTL)
# Missing Content-Length → 411
# Oversize Content-Length (>64MB) → 413
# Malformed seq → 400
# Over daily byte quota → 429
```

## Client-side mapping

Client POSTs `POST /gpd/log` with:

- `Authorization: Bearer <virtual key>`
- `Content-Encoding: gzip`
- `Content-Type: application/x-ndjson`
- Query: `session=<id>&root_session=<id>&seq=<ULID>`
- Body: gzipped NDJSON — one `GpdLog.Event` per line

The server writes the object to:
```
gs://gpd-desktop-logs/user=<hashed_user_id>/date=YYYY-MM-DD/session=<root_id>/parts/<seq>.jsonl.gz
```
or for subagents:
```
gs://gpd-desktop-logs/user=<hashed_user_id>/date=YYYY-MM-DD/session=<root_id>/subagents/agent-<child_id>/parts/<seq>.jsonl.gz
```

A nightly compactor (separate service) fuses `parts/*.jsonl.gz` into
a single `root.jsonl.gz` per session per day, using GCS `Objects.compose()`
in 32-at-a-time batches.

## TOS acceptance — one-time DDL before deploy

`/gpd/tos-accept` writes to the `gpd_tos_acceptance` table in LiteLLM's
Postgres DB. The handler assumes the table exists; the first INSERT
against a missing table returns `503 tos write failed: ...`.

Apply the DDL **before** the first redeploy that ships the `gpd_tos`
package:

```bash
cat infra/litellm/scripts/create-tos-table.sql | \
  railway ssh --service litellm \
    --project 0ddad766-1ee1-44ed-95c2-f8f7d9cb5515 \
    'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f -'
```

Idempotent — safe to re-run.

### TOS endpoint verification

```bash
KEY=sk-<your-key>                                    # must carry a user_id (non-admin)
BASE=https://litellm-production-46bb.up.railway.app

curl -sS -X POST \
  "$BASE/gpd/tos-accept?tos_version=0.0-placeholder&app_version=1.1.10" \
  -H "Authorization: Bearer $KEY" \
  -H "User-Agent: smoke-test/1.0" | jq
# Expected: {"ok": true}

# Verify the row landed
railway ssh --service litellm \
  'psql "$DATABASE_URL" -c "SELECT user_id, key_last4, tos_version, client_ip, accepted_at FROM gpd_tos_acceptance ORDER BY accepted_at DESC LIMIT 5;"'
```

Negative tests:

```bash
# Missing tos_version → 400
# Master / admin key (no user_id) → 401
# tos_version > 64 chars → 400
```
