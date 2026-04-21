-- External table over the GCS bucket.
-- Hive partitioning auto-detects user=<hash> and date=YYYY-MM-DD segments.
-- Everything after `session=<root>/` is path suffix (not a partition).
-- require_hive_partition_filter keeps queries from scanning the whole bucket
-- accidentally; every query must have user= AND date= filters.
CREATE OR REPLACE EXTERNAL TABLE `gpd-desktop.gpd_logs.sessions_external`
(
  ts              INT64,
  kind            STRING,
  v               INT64,
  sessionID       STRING,
  parentSessionID STRING,
  rootSessionID   STRING,
  info            JSON,
  part            JSON,
  diff            JSON,
  reason          STRING,
  spilledBlobSha  STRING
)
WITH PARTITION COLUMNS
OPTIONS (
  format = 'JSON',
  compression = 'GZIP',
  uris = ['gs://gpd-desktop-logs/*'],
  hive_partition_uri_prefix = 'gs://gpd-desktop-logs/',
  require_hive_partition_filter = true,
  ignore_unknown_values = true,
  max_bad_records = 0,
  description = "Raw GPD session events, NDJSON gzipped. Use WHERE user='<hash>' AND date='YYYY-MM-DD' to prune."
);
