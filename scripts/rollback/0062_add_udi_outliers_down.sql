-- Rollback for 0062_add_udi_outliers.sql

DROP INDEX IF EXISTS idx_udi_outliers_status;
DROP INDEX IF EXISTS idx_udi_outliers_reg_no;
DROP INDEX IF EXISTS idx_udi_outliers_source_run_id;
DROP INDEX IF EXISTS uq_udi_outliers_run_reg;
DROP TABLE IF EXISTS udi_outliers;
