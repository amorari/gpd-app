"""Postgres writer for TOS acceptance rows.

Uses LiteLLM's bundled PrismaClient with raw SQL — same pattern as
`infra/litellm/scripts/resolve-env-keys.py:36,49-54,104-110`. We do NOT
fork LiteLLM's prisma/schema.prisma — our custom table lives outside its
managed schema and is created via one-off DDL (see
`infra/litellm/scripts/create-tos-table.sql`).

The `PrismaClient` singleton is lazily initialized on first use. LiteLLM
already connects its own Prisma client at proxy startup; we need our own
handle because LiteLLM's internal client isn't exposed as a module-level
import target.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("gpd_tos.db")

_client = None
_lock = asyncio.Lock()


async def _get_client():
    """Lazily connect a PrismaClient singleton.

    Serialised via an asyncio.Lock so a burst of concurrent first requests
    don't each trigger a connect() — Prisma's client isn't safe against
    concurrent connect() calls.
    """
    global _client
    if _client is not None:
        return _client
    async with _lock:
        if _client is not None:
            return _client
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL env var required for gpd_tos (LiteLLM always sets it)"
            )

        from litellm.proxy.utils import PrismaClient

        c = PrismaClient(database_url=db_url, proxy_logging_obj=None)
        await c.connect()
        _client = c
        logger.info("gpd_tos.db: PrismaClient connected")
        return _client


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

    Parameterised — no SQL injection even though all values except client_ip
    come from untrusted headers/query params (user_agent, app_version).
    client_ip is cast `::inet` on the server — invalid addresses will raise
    and the handler will return 503 to the client. That's preferable to
    silently dropping the row.

    key_hash_last4 is the last 4 chars of LiteLLM's SHA256 token hash
    (what `user_api_key_dict.api_key` exposes), NOT the raw sk-... key the
    user typed. Column was renamed from `key_last4` to reflect this; see
    `infra/litellm/scripts/rename-key-last4.py` for the migration.
    """
    client = await _get_client()
    await client.db.execute_raw(
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
