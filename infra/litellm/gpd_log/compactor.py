"""Nightly compactor: fuse parts/*.jsonl.gz into one root.jsonl.gz per session-day.

Why: client flushes every ~1s (during active subagent fan-out, much faster).
Per-flush objects hit GCS's 1-write/sec-per-object ceiling if we wrote to
a single file. So client writes `parts/<ULID>.jsonl.gz` (unique object per
flush), and this job fuses them at rest.

Fusing strategy: lexicographic part-name order == chronological (ULID is
timestamp-prefixed). Simple concat of gzipped streams works because gzip
is concatenation-safe per RFC 1952 §2.2.

Run modes:
  - Railway cron:    `python -m gpd_log.compactor --yesterday`
  - Cloud Function:  `compact_all()` as the entry point, HTTP trigger
  - Ad-hoc:          `python -m gpd_log.compactor --date 2026-04-20`

What survives: `parts/` is deleted after a successful fuse, leaving just
`root.jsonl.gz`. The lifecycle policy (30d nearline, 90d coldline) then
flows on the compacted object as normal.
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from google.cloud import storage

from .gcs_writer import _get_bucket

log = logging.getLogger("gpd_log.compactor")

# GCS limits: compose() takes up to 32 components. If a session has
# more than 32 parts (subagent-heavy day), we do two passes.
COMPOSE_MAX = 32


def _list_sessions_for_date(bucket: storage.Bucket, date: str) -> list[str]:
    """Return list of object prefixes that look like
    `user=*/date=<date>/session=*/` (one per session).
    """
    # `Client.list_blobs(prefix=..., delimiter="/")` returns prefixes in
    # the response's `prefixes` attr when called via list_blobs with
    # delimiter. We iterate two levels of prefix to enumerate sessions.
    prefixes: set[str] = set()
    for user_prefix in _list_subdirs(bucket, ""):
        if not user_prefix.startswith("user="):
            continue
        date_prefix = f"{user_prefix}date={date}/"
        for session_prefix in _list_subdirs(bucket, date_prefix):
            if session_prefix.startswith(f"{date_prefix}session="):
                prefixes.add(session_prefix)
            # Nested subagent dirs are compacted per-subagent, not per-root.
            # Handle them by walking the tree another level:
            subagents_prefix = f"{session_prefix}subagents/"
            for sub in _list_subdirs(bucket, subagents_prefix):
                prefixes.add(sub)
    return sorted(prefixes)


def _list_subdirs(bucket: storage.Bucket, prefix: str) -> list[str]:
    client = bucket.client
    it = client.list_blobs(bucket, prefix=prefix, delimiter="/")
    # Exhaust iterator to populate `prefixes`.
    list(it)
    return sorted(it.prefixes or [])


def _list_parts(bucket: storage.Bucket, session_prefix: str) -> list[storage.Blob]:
    parts_prefix = f"{session_prefix}parts/"
    blobs = list(bucket.client.list_blobs(bucket, prefix=parts_prefix))
    # Lexicographic == chronological (ULID prefix).
    return sorted(blobs, key=lambda b: b.name)


def _compose_batch(
    bucket: storage.Bucket,
    destination_name: str,
    sources: list[storage.Blob],
) -> storage.Blob:
    dest = bucket.blob(destination_name)
    dest.content_encoding = "gzip"
    dest.content_type = "application/x-ndjson"
    dest.compose(sources)
    return dest


def compact_session(bucket: storage.Bucket, session_prefix: str) -> dict:
    """Fuse parts/*.jsonl.gz → root.jsonl.gz for one session-day.

    Returns {'session': prefix, 'parts': N, 'bytes': M, 'skipped': bool}.
    Idempotent: if root.jsonl.gz already exists and is newer than the
    oldest part, skip.
    """
    parts = _list_parts(bucket, session_prefix)
    if not parts:
        return {"session": session_prefix, "parts": 0, "skipped": True}

    root_name = f"{session_prefix}root.jsonl.gz"
    root = bucket.blob(root_name)
    if root.exists(bucket.client):
        root.reload()
        if root.updated and parts[-1].updated and root.updated > parts[-1].updated:
            return {"session": session_prefix, "parts": len(parts), "skipped": True}

    # Two-phase compose for > 32 parts.
    intermediates: list[storage.Blob] = []
    if len(parts) <= COMPOSE_MAX:
        final_sources = parts
    else:
        batch_idx = 0
        for start in range(0, len(parts), COMPOSE_MAX):
            batch = parts[start : start + COMPOSE_MAX]
            tmp_name = f"{session_prefix}_compact/tmp-{batch_idx:04d}.jsonl.gz"
            intermediates.append(_compose_batch(bucket, tmp_name, batch))
            batch_idx += 1
        final_sources = intermediates

    total_bytes = sum((p.size or 0) for p in parts)
    _compose_batch(bucket, root_name, final_sources)

    # Delete parts only after the compose succeeded — makes the operation
    # resumable if compose fails halfway.
    for p in parts:
        p.delete()
    for i in intermediates:
        i.delete()

    return {"session": session_prefix, "parts": len(parts), "bytes": total_bytes, "skipped": False}


def compact_all(date: str) -> dict:
    bucket = _get_bucket()
    results = []
    for session_prefix in _list_sessions_for_date(bucket, date):
        try:
            r = compact_session(bucket, session_prefix)
            results.append(r)
            log.info("compacted", extra={"result": r})
        except Exception as e:
            log.exception("compact failed", extra={"session": session_prefix})
            results.append({"session": session_prefix, "error": str(e)})
    return {"date": date, "sessions": len(results), "details": results}


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (defaults to yesterday UTC)")
    parser.add_argument("--yesterday", action="store_true")
    args = parser.parse_args()

    if args.date:
        date = args.date
    else:
        date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    t0 = time.time()
    summary = compact_all(date)
    dt = time.time() - t0
    log.info(f"done date={date} sessions={summary['sessions']} elapsed={dt:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
