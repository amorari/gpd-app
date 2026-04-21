-- Insert new rows from the external table into the native sessions table.
-- Scheduled query runs every 6h; re-running is safe because we filter on
-- (ingest_date, source_object) against what's already landed today.
--
-- INVARIANT — do not widen this date window without also moving the
-- compactor window (.github/workflows/compactor.yml) to stay disjoint.
-- Currently: materialize = today. compactor = yesterday.
-- Post-compaction, the same event bytes exist under a new path
-- (session=<root>/root.jsonl.gz vs parts/<ULID>.jsonl.gz), which
-- source_object-based anti-dedupe doesn't catch. Overlapping windows
-- → duplicate rows in gpd_logs.sessions.
--
-- Scheduled query parameterization:
--   @run_date: filled automatically by BigQuery Data Transfer (today UTC).
--   We scan today only. Midnight-spanning sessions whose "yesterday"
--   flushes land after 00:00 UTC would be missed — widen the window
--   here + in the anti-dedupe filter below if that ever matters (it
--   doesn't until we have real users).
INSERT INTO `gpd-desktop.gpd_logs.sessions` (
  ingest_date,
  user_hash,
  ts,
  kind,
  v,
  session_id,
  root_session_id,
  parent_session_id,
  info,
  part,
  diff,
  reason,
  spilled_blob_sha,
  source_object,
  ingested_at
)
WITH
  src AS (
    SELECT
      e.date                               AS ingest_date,
      e.user                               AS user_hash,
      TIMESTAMP_MILLIS(e.ts)               AS ts,
      e.kind                               AS kind,
      e.v                                  AS v,
      COALESCE(
        e.sessionID,
        REGEXP_EXTRACT(_FILE_NAME, r'/session=([^/]+)/')
      )                                    AS session_id,
      COALESCE(
        e.rootSessionID,
        REGEXP_EXTRACT(_FILE_NAME, r'/session=([^/]+)/')
      )                                    AS root_session_id,
      e.parentSessionID                    AS parent_session_id,
      e.info                               AS info,
      e.part                               AS part,
      e.diff                               AS diff,
      e.reason                             AS reason,
      e.spilledBlobSha                     AS spilled_blob_sha,
      _FILE_NAME                           AS source_object,
      CURRENT_TIMESTAMP()                  AS ingested_at
    FROM `gpd-desktop.gpd_logs.sessions_external` AS e
    WHERE e.date = CAST(@run_date AS DATE)
  )
SELECT * FROM src
WHERE source_object NOT IN (
  SELECT source_object
  FROM `gpd-desktop.gpd_logs.sessions`
  WHERE ingest_date = @run_date
);
