"""Per-key daily byte-quota enforcement on top of LiteLLM's built-in RPM.

LiteLLM's rate limiter is RPM/TPM-scoped (token counts for LLM routes).
For /gpd/log we care about **bytes written to GCS per key per day**,
because the abuse we're guarding against is "valid key POSTs 1TB/day of
garbage." Separate Redis counter, keyed by the hash of the bearer token.

Fail-closed on Redis outage: better to refuse log writes temporarily
than to silently let quotas bypass. Client will spill locally and retry.
"""
import hashlib
import os
import time

from fastapi import HTTPException

try:
    import redis.asyncio as aioredis  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — stock LiteLLM image ships redis
    aioredis = None  # type: ignore[assignment]

# Default daily byte cap per virtual key.
# 10 GiB is sized for our motivating example: one Claude Code session at
# 2.5 GB on disk. 1 GiB default would silently truncate such sessions
# (client spills to 1 GiB local cap, then FIFO-drops tail events). 10 GiB
# gives room for several long sessions per day while still catching
# runaway abuse.
DEFAULT_CAP_BYTES = int(os.environ.get("GPD_LOG_BYTES_PER_DAY", 10 * 1024 * 1024 * 1024))
_redis: "aioredis.Redis | None" = None


def _client() -> "aioredis.Redis":
    global _redis
    if _redis is not None:
        return _redis
    if aioredis is None:
        raise RuntimeError("redis.asyncio not available; check LiteLLM image")
    url = (
        os.environ.get("REDIS_URL")
        or os.environ.get("REDIS_HOST_URL")
        or os.environ.get("REDIS_HOST")
    )
    if not url:
        raise RuntimeError("GPD_LOG requires REDIS_URL / REDIS_HOST_URL / REDIS_HOST")
    # Support both full URLs and bare host (LiteLLM sets REDIS_HOST as bare).
    if not url.startswith(("redis://", "rediss://")):
        port = os.environ.get("REDIS_PORT", "6379")
        password = os.environ.get("REDIS_PASSWORD")
        auth = f":{password}@" if password else ""
        url = f"redis://{auth}{url}:{port}"
    _redis = aioredis.from_url(url, decode_responses=False)
    return _redis


async def check_daily_bytes(api_key: str | None, payload_bytes: int) -> None:
    if not api_key:
        raise HTTPException(401, detail="missing api_key on auth object")

    hashed = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:24]
    day = time.strftime("%Y%m%d", time.gmtime())
    counter_key = f"gpd:log:bytes:{hashed}:{day}"

    try:
        c = _client()
        pipe = c.pipeline()
        pipe.incrby(counter_key, payload_bytes)
        pipe.expire(counter_key, 60 * 60 * 26)
        total, _ = await pipe.execute()
    except HTTPException:
        raise
    except Exception as e:  # fail closed — Redis unreachable
        raise HTTPException(503, detail=f"quota service unavailable: {e}") from e

    if total > DEFAULT_CAP_BYTES:
        raise HTTPException(
            429,
            detail=f"daily log byte quota exceeded ({total} > {DEFAULT_CAP_BYTES})",
        )
