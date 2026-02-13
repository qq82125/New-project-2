-- Rollback for migrations/0011_pri1_ivd_model.sql
-- Execute manually when needed.

DROP INDEX IF EXISTS idx_data_cleanup_runs_run_at;
DROP TABLE IF EXISTS data_cleanup_runs;

DROP INDEX IF EXISTS idx_products_ivd_category;
DROP INDEX IF EXISTS idx_products_is_ivd;

ALTER TABLE products DROP COLUMN IF EXISTS ivd_version;
ALTER TABLE products DROP COLUMN IF EXISTS ivd_reason;
ALTER TABLE products DROP COLUMN IF EXISTS ivd_category;
ALTER TABLE products DROP COLUMN IF EXISTS is_ivd;
