-- Insert new rows from the external table into the native sessions table.
-- Scheduled query runs hourly; re-running it is safe because we filter by
-- ingest_date and only insert rows whose (ingest_date, source_object) pair
-- isn't already present. Ingest_date = the Hive `date=` path segment.
--
-- Scheduled query parameterization:
--   @run_date: filled automatically by BigQuery Data Transfer (today UTC).
--   We process yesterday + today on every run so that late-arriving flushes
--   (session spans midnight UTC) get picked up.
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
    WHERE e.date IN (
      CAST(DATE_SUB(@run_date, INTERVAL 1 DAY) AS DATE),
      CAST(@run_date AS DATE)
    )
  )
SELECT * FROM src
WHERE source_object NOT IN (
  SELECT source_object
  FROM `gpd-desktop.gpd_logs.sessions`
  WHERE ingest_date BETWEEN DATE_SUB(@run_date, INTERVAL 2 DAY) AND @run_date
);
