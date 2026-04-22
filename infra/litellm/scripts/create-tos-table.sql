-- gpd_tos_acceptance: append-only audit of Terms-of-Service acceptances.
--
-- Apply once against the LiteLLM Postgres before deploying the
-- gpd_tos Python package. Handler at infra/litellm/gpd_tos/handler.py
-- assumes this table exists; first INSERT will 503 otherwise.
--
-- One-time bootstrap:
--   cat infra/litellm/scripts/create-tos-table.sql | \
--     railway ssh --service litellm \
--       --project 0ddad766-1ee1-44ed-95c2-f8f7d9cb5515 \
--       'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f -'
--
-- Idempotent — safe to re-run (IF NOT EXISTS everywhere).
--
-- Schema is GPD-custom; no LiteLLM_ prefix so it doesn't collide with
-- upstream table-name conventions if LiteLLM ever ships its own TOS
-- tracking.

-- key_hash_last4: last 4 chars of LiteLLM's SHA256 token hash (what
-- user_api_key_dict.api_key exposes), NOT the raw sk-... string the
-- user typed. Useful for cross-reference with LiteLLM_VerificationToken;
-- not usable as a user-facing "key ends in XXXX" display.
CREATE TABLE IF NOT EXISTS gpd_tos_acceptance (
  id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          TEXT         NOT NULL,
  key_hash_last4   TEXT         NOT NULL,
  tos_version      TEXT         NOT NULL,
  app_version      TEXT,
  user_agent       TEXT,
  client_ip        INET,
  accepted_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Lookup pattern: "what's the latest TOS acceptance this user has on
-- record for version X?" — for both debugging and in-app "is this user
-- up to date" checks if we ever add a status endpoint.
CREATE INDEX IF NOT EXISTS idx_gpd_tos_user_version_at
  ON gpd_tos_acceptance (user_id, tos_version, accepted_at DESC);

-- Ops / abuse pattern: "who has accepted recently?" sorted by time.
CREATE INDEX IF NOT EXISTS idx_gpd_tos_accepted_at
  ON gpd_tos_acceptance (accepted_at DESC);
