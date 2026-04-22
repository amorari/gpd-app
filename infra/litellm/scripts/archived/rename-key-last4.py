"""One-shot migration: rename gpd_tos_acceptance.key_last4 → key_hash_last4.

Rationale: the value stored there is the last-4 chars of LiteLLM's
SHA256-hashed bearer token (what `user_api_key_dict.api_key` actually
exposes — not the raw sk-... string the user typed). The original column
name 'key_last4' implied it was last-4 of the user's typed key, which is
misleading for audit/debugging. Renaming to key_hash_last4 makes that
explicit.

Safe because:
  * The canary rows created during smoke-testing have been pruned
    (see show-tos-rows.py — returned 0 rows).
  * No user-facing release is live that writes to this column yet: the
    handler is deployed but the client (1.1.10) just shipped today and
    has not been rolled out to any professor.
  * Postgres ALTER TABLE RENAME COLUMN is atomic and takes an ACCESS
    EXCLUSIVE lock only for microseconds.

Run once via the same `railway ssh` base64 pattern as apply-tos-ddl.py.
Idempotent: checks for the old column name first.
"""
import asyncio, os, sys, asyncpg

async def main():
    url = os.environ["DATABASE_URL"]
    if "?" in url:
        url = url.split("?", 1)[0]
    c = await asyncpg.connect(url)
    try:
        rows = await c.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'gpd_tos_acceptance' AND column_name IN "
            "('key_last4', 'key_hash_last4')"
        )
        names = {r["column_name"] for r in rows}
        print(f"columns present: {sorted(names)}")
        if "key_hash_last4" in names and "key_last4" not in names:
            print("already renamed; nothing to do")
            return 0
        if "key_last4" not in names:
            print("ERROR: neither column found; table schema unexpected", file=sys.stderr)
            return 2
        await c.execute(
            "ALTER TABLE gpd_tos_acceptance RENAME COLUMN key_last4 TO key_hash_last4"
        )
        print("✓ renamed key_last4 → key_hash_last4")
    finally:
        await c.close()
    return 0

sys.exit(asyncio.run(main()))
