# BigQuery analytics for GPD session logs

Two-layer pipeline:

1. **External table** `gpd_logs.sessions_external` — queries NDJSON objects
   directly from `gs://gpd-desktop-logs`. Hive-partitioned on `user` and
   `date` path segments. Flexible but slow-ish (no clustering, no indexes).
2. **Materialized table** `gpd_logs.sessions` — partitioned by `ingest_date`,
   clustered by `(user_hash, session_id)`. Sub-second per-session fetches,
   SEARCH index on string columns for fast pattern queries. Refreshed
   hourly from the external table.

## Setup — one-time

```bash
# 1. External table (reads gs://gpd-desktop-logs/**)
bq query --use_legacy_sql=false --project_id=gpd-desktop \
  < infra/bigquery/01-external-table.sql

# 2. Native clustered table
bq query --use_legacy_sql=false --project_id=gpd-desktop \
  < infra/bigquery/02-materialized-sessions.sql

# 3. SEARCH index on string cols (enables SEARCH() full-text queries)
bq query --use_legacy_sql=false --project_id=gpd-desktop \
  "CREATE SEARCH INDEX IF NOT EXISTS sessions_text_index ON \`gpd-desktop.gpd_logs.sessions\`(kind, session_id, root_session_id, reason) OPTIONS(analyzer='LOG_ANALYZER')"
```

## Scheduled hourly materialize (requires one-time OAuth consent)

The `03-materialize.sql` template inserts new rows from the external table
into the native table. To run it hourly:

```bash
QUERY=$(cat infra/bigquery/03-materialize.sql)
bq mk --transfer_config \
  --data_source=scheduled_query \
  --target_dataset=gpd_logs \
  --project_id=gpd-desktop \
  --location=US \
  --display_name="gpd_logs hourly materialize" \
  --schedule="every 1 hours" \
  --params="{\"query\":$(jq -Rsa . <<< \"$QUERY\"),\"destination_table_name_template\":\"\",\"write_disposition\":\"WRITE_APPEND\"}"
```

First run prompts for a browser OAuth consent (paste URL → paste token back).
Afterward it runs non-interactively as a scheduled background job.

**Alternative (no OAuth required):** Cloud Scheduler + Cloud Function that
shells out to `bq query ... < 03-materialize.sql` on a service-account
credential. Slightly more ops, no OAuth.

## Manual materialize (for ad-hoc + testing)

```bash
bq query --use_legacy_sql=false --project_id=gpd-desktop \
  --parameter='run_date:DATE:2026-04-21' \
  < infra/bigquery/03-materialize.sql
```

The query is idempotent: re-runs skip rows whose `source_object` already
landed in `sessions` (2-day anti-duplicate window).

## Example queries

```sql
-- Reconstruct one session's event stream
SELECT ts, kind, info, part
FROM `gpd-desktop.gpd_logs.sessions`
WHERE ingest_date BETWEEN '2026-04-21' AND '2026-04-22'
  AND session_id = 'ses_abc...'
ORDER BY ts;

-- Per-user activity last 7 days
SELECT user_hash, COUNT(DISTINCT session_id) AS sessions, COUNT(*) AS events
FROM `gpd-desktop.gpd_logs.sessions`
WHERE ingest_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY user_hash
ORDER BY events DESC;

-- Sessions that spawned >10 subagents (interesting!)
SELECT root_session_id, COUNT(DISTINCT session_id) AS subagents
FROM `gpd-desktop.gpd_logs.sessions`
WHERE ingest_date BETWEEN '2026-04-01' AND CURRENT_DATE()
  AND session_id != root_session_id
GROUP BY root_session_id
HAVING subagents > 10
ORDER BY subagents DESC
LIMIT 20;

-- Full-text search
SELECT session_id, ingest_date
FROM `gpd-desktop.gpd_logs.sessions`
WHERE SEARCH((kind, session_id, reason), 'compact-boundary')
LIMIT 50;
```
