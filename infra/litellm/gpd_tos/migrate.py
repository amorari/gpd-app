"""Plain-SQL migrations runner for the gpd_audit database.

Run from `hook.register()` during LiteLLM worker startup via
`await apply_migrations()`. The worker blocks on this awaitable before
serving traffic, so the first POST to /gpd/tos-accept never lands against
a missing table.

Migration files under `infra/litellm/gpd_tos/migrations/NNNN_name.sql`
are applied in lexicographic order, once each. State is tracked in a
`schema_migrations` table in the same database. Idempotent — already-
applied files are skipped.

Why raw SQL + a 50-line runner rather than alembic/sqitch:
  * Zero extra container deps. asyncpg is already there (baked into the
    Dockerfile for `gpd_tos.db`).
  * No ORM model drift — the table is read/written only by asyncpg,
    and the schema is the single source of truth.
  * Works for a one-table audit store. Scale up only if we grow a
    proper data model.

Inside-container loading: the repo's `infra/litellm/gpd_tos/migrations/`
directory is COPYied into /app/gpd_tos/migrations/ via the Dockerfile
(see infra/litellm/Dockerfile). We resolve files via
`importlib.resources.files(__package__).joinpath("migrations")`.
"""
from __future__ import annotations

import logging
import os
from importlib.resources import files
from pathlib import Path
from typing import List, Tuple

import asyncpg

logger = logging.getLogger("gpd_tos.migrate")


def _clean_url(url: str) -> str:
    """Strip Prisma-style `?schema=...` query params asyncpg doesn't parse."""
    return url.split("?", 1)[0] if "?" in url else url


def _audit_url() -> str:
    """Prefer GPD_AUDIT_DATABASE_URL; fall back to DATABASE_URL only as a
    bootstrap safety net so a misconfigured deploy can still write rows to
    the LiteLLM DB temporarily. A warning is logged — ops should set the
    dedicated var to decouple the audit store from LiteLLM's migrations."""
    url = os.environ.get("GPD_AUDIT_DATABASE_URL")
    if url:
        return _clean_url(url)
    fallback = os.environ.get("DATABASE_URL")
    if fallback:
        logger.warning(
            "gpd_tos.migrate: GPD_AUDIT_DATABASE_URL unset; falling back to "
            "DATABASE_URL (LiteLLM's own DB). This is NOT production-safe — "
            "LiteLLM's startup migrator can drop the gpd_tos_acceptance table."
        )
        return _clean_url(fallback)
    raise RuntimeError(
        "gpd_tos.migrate: neither GPD_AUDIT_DATABASE_URL nor DATABASE_URL set"
    )


def _list_migrations() -> List[Tuple[str, str]]:
    """Return [(name, sql)] sorted by filename. Reads from the package
    resource dir so container layouts that don't mirror the repo still
    work."""
    root = files(__package__).joinpath("migrations")
    migs: List[Tuple[str, str]] = []
    for entry in sorted(Path(str(root)).iterdir()):
        if entry.suffix != ".sql":
            continue
        migs.append((entry.name, entry.read_text(encoding="utf-8")))
    if not migs:
        raise RuntimeError(
            "gpd_tos.migrate: no .sql files in migrations/ — migration "
            "bundle is missing from the image (Dockerfile COPY incomplete?)"
        )
    return migs


async def apply_migrations() -> None:
    """Apply any pending migrations. Called exactly once per worker at
    startup. Uses a single connection + a transaction wrapping each file
    so partial failures rollback cleanly."""
    conn = await asyncpg.connect(_audit_url())
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              name       TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            r["name"]
            for r in await conn.fetch("SELECT name FROM schema_migrations")
        }
        for name, sql in _list_migrations():
            if name in applied:
                continue
            logger.info(f"gpd_tos.migrate: applying {name}")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (name) VALUES ($1)", name
                )
            logger.info(f"gpd_tos.migrate: ✓ {name}")
    finally:
        await conn.close()
