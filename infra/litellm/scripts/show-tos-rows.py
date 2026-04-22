"""Dump the 10 most recent gpd_tos_acceptance rows for smoke-test verification.

Connects to the audit DB (GPD_AUDIT_DATABASE_URL), not LiteLLM's own DB.
Falls back to DATABASE_URL with a warning — useful when cutting over, but
in steady state the audit DB should be dedicated."""
import asyncio, os, sys, asyncpg

async def main():
    url = os.environ.get("GPD_AUDIT_DATABASE_URL") or os.environ["DATABASE_URL"]
    if url == os.environ.get("DATABASE_URL"):
        print("WARNING: using DATABASE_URL (LiteLLM's DB); audit rows should live in GPD_AUDIT_DATABASE_URL", file=sys.stderr)
    if "?" in url:
        url = url.split("?", 1)[0]
    c = await asyncpg.connect(url)
    try:
        rows = await c.fetch(
            "SELECT user_id, token_hash_suffix, tos_version, tos_text_sha256, "
            "viewed_in_full, app_version, user_agent, client_ip::text AS ip, "
            "accepted_at, revoked_at "
            "FROM gpd_tos_acceptance ORDER BY accepted_at DESC LIMIT 10"
        )
        print(f"{len(rows)} row(s):")
        for r in rows:
            print(f"  {dict(r)}")
    finally:
        await c.close()

sys.exit(asyncio.run(main()) or 0)
