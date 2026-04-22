"""POST /gpd/tos-accept — record a Terms-of-Service acceptance event.

Auth:   Authorization: Bearer <LiteLLM virtual key> (Depends handles)
Query:  ?tos_version=<version string>
        &app_version=<desktop build version, optional>
Headers captured server-side:
        User-Agent        → truncated to 512 chars
        X-Forwarded-For   → first hop taken as client IP
Out:    {"ok": true}

Writes one append-only row to `gpd_tos_acceptance` with:
  user_id      — from user_api_key_dict (server-derived, not client-settable)
  key_last4    — last 4 chars of the LiteLLM api_key (for cross-reference
                 with LiteLLM_VerificationToken without storing the full key)
  tos_version  — the version the user explicitly agreed to
  app_version  — desktop build that rendered the TOS (optional)
  user_agent   — from the request
  client_ip    — X-Forwarded-For first hop (Railway preserves this)
  accepted_at  — server UTC timestamp (clock skew-proof)

Invariants:
  1. Virtual key is valid & not revoked/expired (Depends user_api_key_auth).
  2. Admin / master keys (user_id empty) are rejected — they cannot collide
     into a single anonymous bucket. Mirrors gpd_log/handler.py:108-113.
  3. Table must exist before the first request. DDL is applied via
     infra/litellm/scripts/create-tos-table.sql (one-time, railway ssh).

Low-volume endpoint: one row per (user, version, device install). No Redis
byte-quota, no pre_call_hook rate-limit — the attack surface is "a valid
virtual key spams accepts" which just inflates the audit table; drop that
key if it ever matters.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

from . import db

_MAX_VERSION_LEN = 64
_MAX_APP_VERSION_LEN = 64
_MAX_USER_AGENT_LEN = 512


async def gpd_tos_accept(
    request: Request,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> dict:
    # Reject admin / master keys. Same rationale as gpd_log/handler.py:
    # without a user_id the acceptance row is anonymous and useless for
    # proving "which user agreed to what". Operators who need to TOS-accept
    # from a scripted context should mint a user-scoped key first.
    user_id = user_api_key_dict.user_id
    if not user_id:
        raise HTTPException(
            401,
            detail="virtual key must carry a user_id (admin keys cannot record TOS acceptance)",
        )

    tos_version = (request.query_params.get("tos_version") or "").strip()
    if not tos_version:
        raise HTTPException(400, detail="tos_version query param required")
    if len(tos_version) > _MAX_VERSION_LEN:
        raise HTTPException(
            400, detail=f"tos_version must be <= {_MAX_VERSION_LEN} chars"
        )

    app_version = (request.query_params.get("app_version") or "").strip() or None
    if app_version and len(app_version) > _MAX_APP_VERSION_LEN:
        raise HTTPException(
            400, detail=f"app_version must be <= {_MAX_APP_VERSION_LEN} chars"
        )

    # Railway's edge proxy preserves the original client IP in
    # X-Forwarded-For; request.client.host would be the internal Railway
    # hop, which is useless for audit.
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        client_ip: str | None = xff.split(",")[0].strip() or None
    else:
        client_ip = request.client.host if request.client else None

    user_agent = (request.headers.get("user-agent") or "")[:_MAX_USER_AGENT_LEN] or None

    api_key = user_api_key_dict.api_key or ""
    key_last4 = api_key[-4:] if len(api_key) >= 4 else api_key

    try:
        await db.insert_acceptance(
            user_id=user_id,
            key_last4=key_last4,
            tos_version=tos_version,
            app_version=app_version,
            user_agent=user_agent,
            client_ip=client_ip,
        )
    except HTTPException:
        raise
    except Exception as e:
        # DB errors are the most likely non-trivial failure here; surface
        # as 503 so the client's retry-on-5xx logic kicks in.
        raise HTTPException(503, detail=f"tos write failed: {e}") from e

    return {"ok": True}
