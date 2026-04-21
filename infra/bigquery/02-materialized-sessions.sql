-- Materialized native table: what analysts + dashboards query against.
-- Partitioned by date (partition pruning on time-range queries), clustered by
-- user and session_id (fast per-user + per-session lookups).
--
-- Refresh strategy: hourly scheduled query INSERTs new rows from the external
-- table for yesterday+today (in case a session spans midnight UTC). See
-- 03-hourly-materialize.sql.
CREATE TABLE IF NOT EXISTS `gpd-desktop.gpd_logs.sessions`
(
  -- Partition columns (promoted from Hive path for fast filtering)
  ingest_date      DATE    NOT NULL,
  user_hash        STRING  NOT NULL,

  -- Event identity
  ts               TIMESTAMP,
  kind             STRING,
  v                INT64,

  -- Session identity — resolved to non-null via the session= path segment
  session_id       STRING,
  root_session_id  STRING,
  parent_session_id STRING,

  -- Typed-ish payload
  info             JSON,
  part             JSON,
  diff             JSON,
  reason           STRING,
  spilled_blob_sha STRING,

  -- GCS lineage — debug aid when a row looks off, you can go fetch the raw
  source_object    STRING,
  ingested_at      TIMESTAMP NOT NULL
)
PARTITION BY ingest_date
CLUSTER BY user_hash, session_id
OPTIONS (
  description = "Materialized session events. Partition by ingest_date, cluster by (user_hash, session_id) for <1s session fetches.",
  partition_expiration_days = 730  -- 2y retention matches GCS lifecycle delete
);
