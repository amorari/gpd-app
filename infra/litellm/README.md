# GPD's LiteLLM image

Ships stock `ghcr.io/berriai/litellm:main-stable` + one custom
route, `POST /gpd/log`, for session-log ingest. The SA key that writes
to `gs://gpd-desktop-logs` lives only on Railway — desktop clients
authenticate with their existing LiteLLM virtual key.

## What's in here

| File | What it does |
|---|---|
| `Dockerfile` | 3-line layer on top of stock LiteLLM |
| `gpd_log/hook.py` | `register()` entry point for `LITELLM_WORKER_STARTUP_HOOKS` |
| `gpd_log/middleware.py` | Rejects requests with missing / oversized Content-Length before the body hits memory |
| `gpd_log/handler.py` | The route: auth → rate-limit → byte-quota → GCS upload |
| `gpd_log/gcs_writer.py` | `upload_from_string(if_generation_match=0)` idempotent write |
| `gpd_log/quota.py` | Per-key daily byte counter in Redis, fail-closed |

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
   GOOGLE_APPLICATION_CREDENTIALS_JSON = <paste the JSON from step above>
   GPD_LOG_BUCKET = gpd-desktop-logs
   GPD_LOG_BYTES_PER_DAY = 1073741824    # 1 GiB/day per key (optional; default)
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
