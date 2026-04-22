"""Print which schema owns gpd_tos_acceptance + current search_path."""
import asyncio, os, sys
from litellm.proxy.utils import PrismaClient

async def main():
    c = PrismaClient(database_url=os.environ["DATABASE_URL"], proxy_logging_obj=None)
    await c.connect()
    try:
        rows = await c.db.query_raw(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_name = 'gpd_tos_acceptance'"
        )
        print("locations of table 'gpd_tos_acceptance':")
        for r in rows:
            print(f"  {r}")
        sp = await c.db.query_raw("SHOW search_path")
        print(f"search_path: {sp}")
        cur = await c.db.query_raw("SELECT current_schema()::text AS s")
        print(f"current_schema: {cur}")
        db = await c.db.query_raw("SELECT current_database()::text AS d")
        print(f"current_database: {db}")
    finally:
        await c.disconnect()

sys.exit(asyncio.run(main()) or 0)
