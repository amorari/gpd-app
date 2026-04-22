"""Resolve `os.environ/<VAR>` references in LiteLLM model api_keys to literals.

Run via:
    cat infra/litellm/scripts/resolve-env-keys.py | \\
      railway ssh --service litellm 'cat > /tmp/resolve.py && python /tmp/resolve.py'

Then bounce the LiteLLM service so the router re-reads the updated rows:
    railway redeploy --service litellm

Context: LiteLLM v1.83.7-stable stores `litellm_params.api_key` as an
encrypted blob that decrypts to the string the user configured (e.g.
`os.environ/ANTHROPIC_API_KEY`). Prior LiteLLM versions resolved the
`os.environ/<VAR>` reference at router init. v1.83.7-stable forwards the
literal string to the upstream provider, which 401s. See
`docs/LITELLM_OPS.md` for full context.

This script is the canonical fix until an upstream release restores env
resolution. Idempotent: re-running is a no-op once literals are in place,
unless upstream env vars rotated.

Safety:
  - Only touches rows whose decrypted api_key starts with `os.environ/`.
    Rows already holding literals are left alone.
  - Prints the before-after for every mutation (stdout log is the audit).
  - Dry-run by default. Pass CONFIRM=1 in env to actually write.
"""
import asyncio
import json
import os
import sys

from litellm.proxy.common_utils.encrypt_decrypt_utils import (
    decrypt_value_helper,
    encrypt_value_helper,
)
from litellm.proxy.utils import PrismaClient


async def main() -> int:
    confirm = os.environ.get("CONFIRM", "") == "1"
    mode = "EXECUTING" if confirm else "DRY RUN (set CONFIRM=1 to apply)"
    print(f"--- resolve-env-keys.py [{mode}] ---")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set in container env", file=sys.stderr)
        return 2

    client = PrismaClient(database_url=db_url, proxy_logging_obj=None)
    await client.connect()
    try:
        rows = await client.db.query_raw(
            'SELECT model_id, model_name, litellm_params::text FROM "LiteLLM_ProxyModelTable"'
        )
        print(f"scanning {len(rows)} model rows")

        mutations: list[tuple[str, str, str, str]] = []  # (model_id, model_name, old_ref, var)

        for r in rows:
            model_id = r["model_id"]
            model_name = r["model_name"]
            lp = json.loads(r["litellm_params"])
            enc_key = lp.get("api_key")
            if not enc_key:
                continue

            # api_key is stored encrypted. Decrypt to see the original reference.
            try:
                decrypted = decrypt_value_helper(value=enc_key, key="api_key")
            except Exception as e:
                print(f"  [skip] {model_name} {model_id}: decrypt failed: {e}")
                continue

            if not isinstance(decrypted, str) or not decrypted.startswith("os.environ/"):
                # Already a literal, or some other shape; leave alone.
                continue

            var_name = decrypted[len("os.environ/"):]
            resolved = os.environ.get(var_name)
            if not resolved:
                print(f"  [skip] {model_name}: references {var_name} but it's not set")
                continue

            mutations.append((model_id, model_name, decrypted, var_name))

        print(f"planned mutations: {len(mutations)}")
        for model_id, model_name, old_ref, var in mutations:
            print(f"  {model_name:40s} [{model_id}] {old_ref} → literal from ${var}")

        if not confirm:
            print("--- DRY RUN — re-run with CONFIRM=1 to apply ---")
            return 0

        if not mutations:
            print("nothing to do")
            return 0

        updated = 0
        for model_id, model_name, _old_ref, var in mutations:
            literal = os.environ[var]
            new_enc = encrypt_value_helper(value=literal)

            # JSON-path update: rewrite only litellm_params.api_key, leave rest intact.
            await client.db.execute_raw(
                'UPDATE "LiteLLM_ProxyModelTable" '
                "SET litellm_params = jsonb_set(litellm_params, '{api_key}', to_jsonb($1::text)) "
                "WHERE model_id = $2",
                new_enc,
                model_id,
            )
            updated += 1
            print(f"  ✓ {model_name} [{model_id}] updated")

        print(f"--- done: {updated} rows updated ---")
        print("NEXT: `railway redeploy --service litellm` so the router re-reads.")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
