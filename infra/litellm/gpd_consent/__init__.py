"""GPD consent gate — blocks LLM calls for users who revoked TOS consent.

Registered as a LiteLLM `CustomLogger` so `async_pre_call_hook` fires on every
LLM API route plus the custom `/gpd/log` pass-through. Raises HTTPException
403 when the caller's `user_id` has a non-null `revoked_at` row in
`gpd_tos_acceptance`, 503 when the audit DB is unreachable (fail-closed).

Without this gate, `/gpd/tos-revoke` writes `revoked_at` to Postgres but
`/chat/completions` + `/gpd/log` never consult it, so "revoke" is cosmetic.
"""
