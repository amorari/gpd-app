"""Dump the 10 most recent gpd_tos_acceptance rows for smoke-test verification."""
import asyncio, os, sys, asyncpg

async def main():
    url = os.environ["DATABASE_URL"]
    if "?" in url:
        url = url.split("?", 1)[0]
    c = await asyncpg.connect(url)
    try:
        rows = await c.fetch(
            "SELECT user_id, key_hash_last4, tos_version, app_version, "
            "user_agent, client_ip::text AS ip, accepted_at "
            "FROM gpd_tos_acceptance ORDER BY accepted_at DESC LIMIT 10"
        )
        print(f"{len(rows)} row(s):")
        for r in rows:
            print(f"  {dict(r)}")
    finally:
        await c.close()

sys.exit(asyncio.run(main()) or 0)
