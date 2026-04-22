-- 0002_privacy_sha.sql — add privacy_text_sha256.
--
-- GDPR Art. 7(2) requires that privacy consent be distinguishable from
-- contract acceptance. The UI now renders two separate scroll+checkbox
-- affordances (one for TOS, one for Privacy Policy), and each acceptance
-- row captures the SHA256 of BOTH documents the user saw.
--
-- Nullable so the rows written by 0001 (no privacy hash available) don't
-- need a placeholder value. New inserts after this migration are required
-- to include privacy_text_sha256 at the handler level.

ALTER TABLE gpd_tos_acceptance
  ADD COLUMN IF NOT EXISTS privacy_text_sha256 TEXT;
