"""Audit-DB query for revocation status.

Reuses the asyncpg pool opened by `gpd_tos.db` so we don't multiply the
per-worker connection count. Both packages point at the same
`GPD_AUDIT_DATABASE_URL`; each worker holds 1-4 connections total regardless
of how many callers import from either module.

Fail-closed by design: any query error (DB unreachable, schema drift,
auth failure) propagates out of `is_revoked()` so the consent_gate caller
can map it to HTTP 503. Silently returning False here would let revoked
users continue making LLM calls during an audit-DB outage — legally worse
than a brief service interruption.
"""
from __future__ import annotations

import logging

from gpd_tos import db as tos_db

logger = logging.getLogger("gpd_consent.db")


async def is_revoked(user_id: str) -> bool:
    """Return True iff any `gpd_tos_acceptance` row for this user has a
    non-null `revoked_at`.

    `mark_revoked` (gpd_tos/db.py:111) stamps every non-revoked row for the
    user in a single UPDATE. Once a user revokes, *all* their historical
    rows carry `revoked_at`. A later re-acceptance INSERTs a fresh row with
    `revoked_at IS NULL`, so this query returning True means "there exists
    a revocation the user has NOT superseded with a later acceptance."

    Implementation: sort by `accepted_at DESC` and look at the newest row.
    If its `revoked_at` is non-null, the user is revoked. If null, the most
    recent action was an accept (possibly after prior revokes) — allow
    through."""
    pool = await tos_db._get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT revoked_at IS NOT NULL AS is_revoked
              FROM gpd_tos_acceptance
             WHERE user_id = $1
             ORDER BY accepted_at DESC
             LIMIT 1
            """,
            user_id,
        )
        if row is None:
            # No acceptance row at all — user has never accepted. Block:
            # any LLM call from a user without an acceptance record is a
            # bug (either they bypassed the client TOS gate or the accept
            # insert failed). Prefer visible error over silent pass-through.
            return True
        return bool(row["is_revoked"])
