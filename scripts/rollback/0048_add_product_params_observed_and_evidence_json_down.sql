-- Rollback for 0048_add_product_params_observed_and_evidence_json.sql

DROP INDEX IF EXISTS idx_product_params_observed_at;
ALTER TABLE product_params
    DROP COLUMN IF EXISTS observed_at,
    DROP COLUMN IF EXISTS evidence_json;
