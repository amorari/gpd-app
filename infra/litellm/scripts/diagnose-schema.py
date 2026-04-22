"""Print where gpd_tos_acceptance lives — used to debug cross-DB mismatches
(e.g., table in LiteLLM DB, handler connecting to audit DB, or vice versa).

Queries both GPD_AUDIT_DATABASE_URL (if set) and DATABASE_URL so you can
see at a glance which DB has the table and which is missing it."""
import asyncio, os, sys, asyncpg


async def probe(label, url):
    if not url:
        print(f"--- {label}: not set ---")
        return
    if "?" in url:
        url = url.split("?", 1)[0]
    try:
        c = await asyncpg.connect(url)
    except Exception as e:
        print(f"--- {label}: connect failed: {e} ---")
        return
    try:
        db = await c.fetchval("SELECT current_database()")
        rows = await c.fetch(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'gpd_tos_acceptance'"
        )
        print(f"--- {label} (database={db}) ---")
        print(f"  locations: {[r['table_schema'] for r in rows] or '(missing)'}")
        if rows:
            cols = await c.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'gpd_tos_acceptance' "
                "ORDER BY ordinal_position"
            )
            print(f"  columns: {[r['column_name'] for r in cols]}")
    finally:
        await c.close()


async def main():
    await probe("GPD_AUDIT_DATABASE_URL", os.environ.get("GPD_AUDIT_DATABASE_URL"))
    await probe("DATABASE_URL (LiteLLM)", os.environ.get("DATABASE_URL"))


sys.exit(asyncio.run(main()) or 0)
