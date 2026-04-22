-- 0001_init.sql — initial TOS acceptance schema.
--
-- Applied by infra/litellm/gpd_tos/migrate.py against GPD_AUDIT_DATABASE_URL,
-- a Postgres database dedicated to legal-audit records. We keep this OUT of
-- LiteLLM's managed DB because LiteLLM's startup `prisma migrate` drops
-- unmanaged tables — storing legal-evidence records there means every
-- redeploy is a chance to lose consent proofs. Separate DB eliminates
-- that coupling.
--
-- Row columns:
--   user_id          — LiteLLM user id (server-derived, never client-settable)
--   token_hash_suffix— first 16 hex of LiteLLM's SHA256 token hash. 16 chars
--                      = 64 bits, room for ~4.3B users at 50% collision risk.
--                      (Full 64-char hash is also available if we ever need
--                      stronger joinability; we retain this column for size.)
--   tos_version      — string identifier the user explicitly agreed to
--   tos_text_sha256  — SHA256 hex of the exact TOS_TEXT the user saw. Ties
--                      the acceptance back to literal text even if the
--                      source file is later edited (git history is
--                      rewritable; MIT-licensed repo users build from
--                      source). Without this, "I never agreed to clause 7"
--                      has no definitive answer.
--   viewed_in_full   — did the user scroll the TOS region to its bottom
--                      before ticking agree? Counters Specht-v.-Netscape
--                      "never saw it" defence. NULL only for legacy rows
--                      from before this column existed; new inserts
--                      require it.
--   app_version      — GPD desktop build at acceptance time
--   user_agent       — request UA, truncated
--   client_ip        — extracted from X-Forwarded-For LAST hop (Railway's
--                      edge appends the real client IP to the end of any
--                      client-supplied chain; taking first would be
--                      attacker-controlled). INET; NULL if parse failed
--                      (rare — see handler.py fallback).
--   accepted_at      — server UTC timestamp. The legal moment.
--   revoked_at       — set by `/gpd/tos-revoke`. Once set, the row is NOT
--                      deleted — it's a revocation record. GDPR Art.
--                      17(3)(e) exception for audit retention.

CREATE TABLE IF NOT EXISTS gpd_tos_acceptance (
  id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              TEXT         NOT NULL,
  token_hash_suffix    TEXT         NOT NULL,
  tos_version          TEXT         NOT NULL,
  tos_text_sha256      TEXT         NOT NULL,
  viewed_in_full       BOOLEAN      NOT NULL DEFAULT FALSE,
  app_version          TEXT,
  user_agent           TEXT,
  client_ip            INET,
  accepted_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
  revoked_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_gpd_tos_user_version_at
  ON gpd_tos_acceptance (user_id, tos_version, accepted_at DESC);

CREATE INDEX IF NOT EXISTS idx_gpd_tos_accepted_at
  ON gpd_tos_acceptance (accepted_at DESC);
