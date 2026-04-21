"""Upload the /gpd/log request body to GCS.

Idempotent: `if_generation_match=0` means "create iff object does not
exist". A client-side spill retry that duplicates the object path gets
a 412 Precondition Failed, which we treat as success. Combined with
monotonic per-flush ULID object names, this gives at-least-once
delivery with exactly-once storage.

Credentials: `GOOGLE_APPLICATION_CREDENTIALS_JSON` env var (inline SA
JSON, Railway-standard). Falls back to Application Default Credentials
if unset, for local testing against gcloud auth login.
"""
from __future__ import annotations

import asyncio
import json
import os

from google.cloud import storage
from google.oauth2 import service_account

_client: storage.Client | None = None
_bucket: storage.Bucket | None = None


def _get_bucket() -> storage.Bucket:
    global _client, _bucket
    if _bucket is not None:
        return _bucket

    bucket_name = os.environ.get("GPD_LOG_BUCKET")
    if not bucket_name:
        raise RuntimeError("GPD_LOG_BUCKET env var required")

    sa_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
        )
        _client = storage.Client(credentials=creds, project=info.get("project_id"))
    else:
        _client = storage.Client()

    _bucket = _client.bucket(bucket_name)
    return _bucket


async def stream_to_gcs(object_path: str, body: bytes) -> int:
    """Upload body as a GCS object at `object_path`.

    Returns bytes written. Treats 412 (object exists) as success to make
    client-side retry-from-spill safe.
    """
    bucket = _get_bucket()
    blob = bucket.blob(object_path)
    # Client sends gzipped NDJSON — preserve that encoding on the stored object
    # so BigQuery's external-table reader (NEWLINE_DELIMITED_JSON) auto-decodes
    # transparently via the .gz suffix.
    blob.content_encoding = "gzip"
    blob.content_type = "application/x-ndjson"

    def _upload() -> int:
        try:
            blob.upload_from_string(
                body,
                content_type="application/x-ndjson",
                if_generation_match=0,
                retry=None,
            )
            return len(body)
        except Exception as e:
            msg = str(e)
            # 412 Precondition Failed → object already exists. Client is
            # retrying a previously-successful write. Idempotent.
            if "preconditionFailed" in msg or "412" in msg:
                return len(body)
            raise

    return await asyncio.to_thread(_upload)
