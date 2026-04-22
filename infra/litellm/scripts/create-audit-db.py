"""One-shot: create the `gpd_audit` logical database on Railway Postgres.

Runs inside the LiteLLM container via railway ssh base64-pipe. Connects
to the admin DB (whatever DATABASE_URL points at — typically `railway`),
then issues `CREATE DATABASE gpd_audit` OUTSIDE a transaction (Postgres
disallows CREATE DATABASE inside a txn).

Idempotent: checks pg_database first and skips if the DB already exists.

After this lands, the operator must:
  1. Construct GPD_AUDIT_DATABASE_URL from DATABASE_URL by swapping the
     final path segment from `/railway` to `/gpd_audit` (or whatever
     dbname the admin URL uses).
  2. Set it as a Railway env var on the litellm service.
  3. Redeploy; startup hook runs migrations against the new DB.
"""
import asyncio, os, sys, asyncpg


async def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL unset", file=sys.stderr)
        return 2
    if "?" in url:
        url = url.split("?", 1)[0]

    # asyncpg connects to the admin DB (railway). We need the host:port
    # to emit the suggested audit URL below.
    c = await asyncpg.connect(url)
    try:
        exists = await c.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'gpd_audit'"
        )
        if exists:
            print("gpd_audit already exists; skipping CREATE DATABASE")
        else:
            # CREATE DATABASE must run outside a transaction; asyncpg
            # runs it in autocommit by default when not wrapped in
            # conn.transaction().
            await c.execute("CREATE DATABASE gpd_audit")
            print("✓ CREATE DATABASE gpd_audit")

        # Print what the operator should set as GPD_AUDIT_DATABASE_URL.
        # Swap the path from /railway → /gpd_audit in the current URL.
        # This is a hint; the operator can also construct the URL from
        # Railway's service variables UI.
        suggested = url
        # Separate path from query (we stripped query earlier, but be safe).
        if "/railway" in suggested:
            suggested = suggested.rsplit("/railway", 1)[0] + "/gpd_audit"
        elif suggested.count("/") >= 3:
            root, _sep, _old = suggested.rpartition("/")
            suggested = root + "/gpd_audit"
        print(f"\nGPD_AUDIT_DATABASE_URL={suggested}")
        print("\nSet that as a Railway env var on the litellm service, then redeploy.")
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
