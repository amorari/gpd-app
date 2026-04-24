"""In-process TTL cache for per-user revocation status.

Per-worker dict. On a 4-worker deploy, a revocation propagates to all workers
within at most the TTL window (default 300s). That matches the Privacy Policy
claim "processing halts after withdrawal" with a <=5-minute operational lag
per worker. If legal requires immediate global invalidation, swap this for
Redis pub/sub (see module-level NOTE in hook.py).

Thread model: LiteLLM workers run under uvicorn with one event loop per
worker process. asyncio.Lock is correct; no threading.Lock needed. On worker
restart / redeploy, the dict resets — revocation is re-queried on next call.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional, Tuple

_DEFAULT_TTL_SECONDS = 300.0

# Maps user_id → (is_revoked, expires_at_monotonic). `is_revoked` is a plain
# bool; absence of an entry means "cache miss, must query DB".
_cache: Dict[str, Tuple[bool, float]] = {}
_lock = asyncio.Lock()


async def get(user_id: str) -> Optional[bool]:
    """Return cached revoked-status, or None on cache miss / expired entry.

    Expired entries are evicted eagerly so the dict doesn't grow without
    bound for users who churn through the system once and never return."""
    async with _lock:
        entry = _cache.get(user_id)
        if entry is None:
            return None
        is_revoked, expires_at = entry
        if time.monotonic() >= expires_at:
            _cache.pop(user_id, None)
            return None
        return is_revoked


async def set(user_id: str, is_revoked: bool, ttl: float = _DEFAULT_TTL_SECONDS) -> None:
    async with _lock:
        _cache[user_id] = (is_revoked, time.monotonic() + ttl)


async def invalidate(user_id: str) -> None:
    """Force-evict one user. Called from /gpd/tos-revoke handler so the user's
    OWN worker drops the cached 'not revoked' entry immediately on revoke.
    Other workers still lag by up to one TTL window."""
    async with _lock:
        _cache.pop(user_id, None)


async def clear() -> None:
    """Test helper. Never call from request path — hot-path clear would
    thunder on the DB for the next N requests."""
    async with _lock:
        _cache.clear()
