"""Postgres writer for TOS acceptance rows.

We use asyncpg directly (not LiteLLM's bundled PrismaClient) for two reasons:

1. `PrismaClient.db.execute_raw()` silently rolls DDL back on disconnect,
   so `ensure_schema()` can't reliably CREATE TABLE that way.
2. LiteLLM's startup `prisma migrate deploy` step drops unmanaged tables
   between deploys, so we need to (re-)create `gpd_tos_acceptance` in
   every worker's startup — `ensure_schema()` runs from hook.register().

asyncpg is baked into the Dockerfile so the import is always satisfied.

The connection pool is lazily opened on first use. We keep a small pool
(1..4) because TOS traffic is very low-volume (one row per user per
version per device); a larger pool would waste file descriptors.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger("gpd_tos.db")

_pool: Optional[asyncpg.Pool] = None
_lock = asyncio.Lock()


def _clean_url(url: str) -> str:
    """Strip the ?schema=... (and other) query params Prisma uses.

    asyncpg doesn't understand them and will reject the URL outright.
    The `schema` param was irrelevant to our use anyway — the table
    lives in `public` by default.
    """
    return url.split("?", 1)[0] if "?" in url else url


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _lock:
        if _pool is not None:
            return _pool
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL env var required for gpd_tos "
                "(LiteLLM always sets it on Railway)"
            )
        _pool = await asyncpg.create_pool(_clean_url(db_url), min_size=1, max_size=4)
        logger.info("gpd_tos.db: asyncpg pool connected")
        return _pool


_DDL = [
    """
    CREATE TABLE IF NOT EXISTS gpd_tos_acceptance (
      id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id          TEXT         NOT NULL,
      key_hash_last4   TEXT         NOT NULL,
      tos_version      TEXT         NOT NULL,
      app_version      TEXT,
      user_agent       TEXT,
      client_ip        INET,
      accepted_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_gpd_tos_user_version_at
      ON gpd_tos_acceptance (user_id, tos_version, accepted_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_gpd_tos_accepted_at
      ON gpd_tos_acceptance (accepted_at DESC)
    """,
]


async def ensure_schema() -> None:
    """(Re-)create gpd_tos_acceptance and its indexes if absent.

    Called from the worker startup hook so every redeploy restores the
    table — LiteLLM's startup migrations drop unmanaged tables, which
    would otherwise leave the first POST 503-ing with "relation does
    not exist".

    Idempotent (IF NOT EXISTS everywhere). Uses a dedicated connection
    (not the pool) so the DDL runs in implicit autocommit before the
    pool is warmed.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL env var required for gpd_tos.ensure_schema")
    conn = await asyncpg.connect(_clean_url(db_url))
    try:
        for stmt in _DDL:
            await conn.execute(stmt)
        logger.info("gpd_tos.db: ensure_schema() ok — gpd_tos_acceptance ready")
    finally:
        await conn.close()


async def insert_acceptance(
    *,
    user_id: str,
    key_hash_last4: str,
    tos_version: str,
    app_version: Optional[str],
    user_agent: Optional[str],
    client_ip: Optional[str],
) -> None:
    """INSERT one row into gpd_tos_acceptance.

    client_ip is cast `::inet` on the server — invalid addresses raise
    and the handler returns 503 to the client. Preferable to silently
    dropping the row.

    key_hash_last4 is the last 4 chars of LiteLLM's SHA256 token hash
    (what `user_api_key_dict.api_key` exposes), NOT the raw sk-... key
    the user typed. See `infra/litellm/scripts/rename-key-last4.py` for
    the rename migration.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO gpd_tos_acceptance (
              user_id, key_hash_last4, tos_version, app_version,
              user_agent, client_ip
            ) VALUES (
              $1, $2, $3, $4,
              $5, $6::inet
            )
            """,
            user_id,
            key_hash_last4,
            tos_version,
            app_version,
            user_agent,
            client_ip,
        )
