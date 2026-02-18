-- Rollback for migrations/0039_add_lri_query_indexes.sql

DROP INDEX IF EXISTS idx_lri_scores_lri_norm_desc;
DROP INDEX IF EXISTS idx_lri_scores_registration_id_calculated_at_desc;

