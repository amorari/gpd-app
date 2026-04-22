"""Apply gpd_tos_acceptance DDL against LiteLLM's Postgres via asyncpg.

LiteLLM's Docker image doesn't ship psql, and PrismaClient.execute_raw()
silently wraps DDL in a transaction that rolls back on disconnect() —
which is why an earlier attempt appeared to succeed (SELECT COUNT(*)
worked within the same connection) but left no table behind.

asyncpg is already in LiteLLM's image. It runs in implicit autocommit
outside a transaction block, so DDL persists as you'd expect.

Usage (from repo root):
    B64=$(base64 -i infra/litellm/scripts/apply-tos-ddl.py | tr -d '\\n') && \\
      railway ssh --service litellm \\
        --project 0ddad766-1ee1-44ed-95c2-f8f7d9cb5515 \\
        "echo '$B64' | base64 -d > /tmp/apply-tos-ddl.py && python /tmp/apply-tos-ddl.py"

Idempotent: each CREATE uses IF NOT EXISTS.
"""
import asyncio
import os
import sys

import asyncpg


DDL_STATEMENTS = [
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


async def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    # asyncpg doesn't understand the ?schema=... param Prisma uses, and
    # rejects unknown query params. Strip them.
    if "?" in db_url:
        db_url = db_url.split("?", 1)[0]

    conn = await asyncpg.connect(db_url)
    try:
        for i, stmt in enumerate(DDL_STATEMENTS, 1):
            label = stmt.strip().splitlines()[0].strip()
            print(f"[{i}/{len(DDL_STATEMENTS)}] {label}")
            await conn.execute(stmt)
            print("    ok")

        row = await conn.fetchrow(
            "SELECT COUNT(*)::int AS n FROM gpd_tos_acceptance"
        )
        print(f"--- gpd_tos_acceptance ready. current row count: {row['n']} ---")

        # Double-check the table is visible outside this connection by
        # querying information_schema.
        schema_rows = await conn.fetch(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'gpd_tos_acceptance'"
        )
        for r in schema_rows:
            print(f"    visible in schema: {r['table_schema']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
