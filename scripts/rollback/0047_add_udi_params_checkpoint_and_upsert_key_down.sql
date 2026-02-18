-- Rollback for 0047_add_udi_params_checkpoint_and_upsert_key.sql

DROP INDEX IF EXISTS uq_product_params_allowlist_product_code;
DROP INDEX IF EXISTS idx_product_params_product_id;
ALTER TABLE product_params DROP COLUMN IF EXISTS product_id;

ALTER TABLE param_dictionary_candidates DROP COLUMN IF EXISTS sample_meta;

DROP INDEX IF EXISTS idx_udi_jobs_checkpoint_updated_at;
DROP TABLE IF EXISTS udi_jobs_checkpoint;
