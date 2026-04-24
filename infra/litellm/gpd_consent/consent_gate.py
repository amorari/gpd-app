"""CustomLogger subclass enforcing TOS consent on every LLM call.

Hooks into LiteLLM's proxy pre-call chain (`litellm.callbacks`). The proxy
invokes `async_pre_call_hook` once per request at
`litellm/proxy/common_request_processing.py:823` for every LLM API route
(completions, embeddings, moderation, speech, transcription, pass-through).
Raising HTTPException here rejects the request before it reaches the
provider — no tokens billed, no provider request made.

Admin keys (master key, no `user_id`) are skipped: they don't represent
end-users, so revocation doesn't apply. This matches how `/gpd/tos-accept`
rejects admin keys at handler level.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Union

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

from . import cache, db

logger = logging.getLogger("gpd_consent")


class ConsentGateLogger(CustomLogger):
    """Blocks requests whose `user_id` has an outstanding revocation."""

    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,  # DualCache — LiteLLM's own, unrelated to our TTL cache
        data: dict,
        call_type: str,
    ) -> Optional[Union[Exception, str, dict]]:
        user_id = getattr(user_api_key_dict, "user_id", None)
        if not user_id:
            # Master key / admin operations. No consent record applies.
            return None

        # Cache lookup first. 300s TTL per worker. On a revoke, the
        # handler calls `cache.invalidate(user_id)` on ITS worker; other
        # workers lag by up to the TTL window.
        cached = await _cache_get(user_id)
        if cached is True:
            raise HTTPException(
                status_code=403,
                detail="consent_revoked: TOS consent withdrawn — "
                "re-accept via the desktop app to resume.",
            )
        if cached is False:
            return None

        # Cache miss — query the audit DB. Fail-closed on any error.
        try:
            revoked = await db.is_revoked(user_id)
        except Exception:
            # Do not log user_id at WARNING; it's a stable pseudonym but
            # still pseudonymous PII in the proxy logs. Log the class only.
            logger.exception("gpd_consent: audit DB query failed; failing closed")
            raise HTTPException(
                status_code=503,
                detail="consent_check_unavailable: audit system is unreachable.",
            )

        await _cache_set(user_id, revoked)
        if revoked:
            raise HTTPException(
                status_code=403,
                detail="consent_revoked: TOS consent withdrawn — "
                "re-accept via the desktop app to resume.",
            )
        return None


# Thin wrappers to keep the `cache` parameter-shadowing in
# `async_pre_call_hook` from fighting `import cache`. LiteLLM's signature
# passes its own `DualCache` positional-or-keyword named `cache`; renaming
# it would break future upstream compat.
async def _cache_get(user_id: str) -> Optional[bool]:
    return await cache.get(user_id)


async def _cache_set(user_id: str, is_revoked: bool) -> None:
    await cache.set(user_id, is_revoked)
