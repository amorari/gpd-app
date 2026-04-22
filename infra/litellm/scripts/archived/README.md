# Archived one-shot migration scripts

Kept for audit / historical reference. **Do not run these against prod.**
The work each script performed is now either handled automatically by the
`gpd_tos` package's startup migrations or has been superseded by a cleaner
mechanism.

| Script | What it did | Superseded by |
|---|---|---|
| `apply-tos-ddl.py` | Created `gpd_tos_acceptance` table + indexes via asyncpg. | `infra/litellm/gpd_tos/migrate.py` runs automatically from the startup hook (awaited, blocking) and applies files under `infra/litellm/gpd_tos/migrations/`. |
| `rename-key-last4.py` | One-time `ALTER TABLE … RENAME COLUMN key_last4 TO key_hash_last4` migration. | The column was renamed again to `token_hash_suffix` (16 chars instead of 4) in migration `0001_init.sql`, which lands in the new **separate audit database** (`GPD_AUDIT_DATABASE_URL`). Neither column name exists in the target DB anymore. |

Both scripts were committed alongside their migrations so the next operator
could reproduce what happened. They are no longer load-bearing.
