"""POST /gpd/log — write session log events to GCS on the user's behalf.

Auth:  Authorization: Bearer <LiteLLM virtual key> (Depends handles)
Input: gzipped NDJSON body (client-produced session events)
Query: ?session=<current session id>
       &root_session=<root of parent chain>   (defaults to session)
       &seq=<26-char ULID>                    (one per flush, monotonic)
Out:   {"ok": true, "path": "user=.../parts/<seq>.jsonl.gz", "bytes": N}

Invariants enforced here:
  1. Virtual key is valid & not revoked/expired (Depends user_api_key_auth).
  2. Per-key daily byte quota via Redis, fail-closed on Redis outage.
  3. User path prefix is derived from user_api_key_dict, never from the
     request body/query — protects against one user writing under another
     user's prefix.
  4. Content-Length ≤ 64MB (enforced by GpdLogMiddleware before we run).
  5. LiteLLM's existing RPM/TPM limiter fires via pre_call_hook.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

from .gcs_writer import stream_to_gcs
from .quota import check_daily_bytes

# Crockford base32 alphabet, as used by ULIDs.
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
# OpenCode session IDs are `ses_<ulid>`-shape; accept alphanumeric + `_-`.
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


async def gpd_log(
    request: Request,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> dict:
    # Rate limit (reuses LiteLLM's existing RPM/TPM descriptors — keyed by
    # api_key/user/team/org, shared with /v1/chat/completions quotas).
    from litellm.proxy.proxy_server import proxy_logging_obj

    await proxy_logging_obj.pre_call_hook(
        user_api_key_dict=user_api_key_dict,
        data={"model": "gpd-log"},
        call_type="pass_through_endpoint",
    )

    # Content-Length was validated by middleware — re-read for the quota counter.
    cl = int(request.headers.get("content-length", "0"))
    await check_daily_bytes(user_api_key_dict.api_key, cl)

    # Validate query params.
    session_id = (request.query_params.get("session") or "").strip()
    root_session_id = (request.query_params.get("root_session") or session_id).strip()
    seq = (request.query_params.get("seq") or "").strip()

    if not _SESSION_RE.match(session_id):
        raise HTTPException(400, detail="invalid or missing 'session' query param")
    if not _SESSION_RE.match(root_session_id):
        raise HTTPException(400, detail="invalid 'root_session' query param")
    if not _ULID_RE.match(seq):
        raise HTTPException(400, detail="'seq' must be a 26-char ULID")

    # User prefix is derived server-side, NEVER from the request body/query.
    # Prefer user_id (stable across key rotations); fall back to hashed token.
    identity = user_api_key_dict.user_id or user_api_key_dict.api_key or ""
    if not identity:
        raise HTTPException(401, detail="auth object carries no user_id or api_key")
    user_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]

    # Build object path.
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if session_id == root_session_id:
        object_path = (
            f"user={user_hash}/date={date}/session={root_session_id}/"
            f"parts/{seq}.jsonl.gz"
        )
    else:
        object_path = (
            f"user={user_hash}/date={date}/session={root_session_id}/"
            f"subagents/agent-{session_id}/parts/{seq}.jsonl.gz"
        )

    # Read body (middleware already capped at 64MB). user_api_key_auth has
    # already drained the ASGI stream, so request.body() returns cached bytes.
    body = await request.body()

    try:
        written = await stream_to_gcs(object_path, body)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=f"gcs write failed: {e}") from e

    return {"ok": True, "path": object_path, "bytes": written}
