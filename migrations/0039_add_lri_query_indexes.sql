-- LRI query perf: indexes to support DISTINCT ON (registration_id ORDER BY calculated_at desc)
-- and dashboard ordering by lri_norm.
--
-- Idempotent. Rollback script: scripts/rollback/0039_add_lri_query_indexes_down.sql

CREATE INDEX IF NOT EXISTS idx_lri_scores_registration_id_calculated_at_desc
    ON lri_scores (registration_id, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_lri_scores_lri_norm_desc
    ON lri_scores (lri_norm DESC);

