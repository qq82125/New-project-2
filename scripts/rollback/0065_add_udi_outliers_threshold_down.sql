-- Rollback for 0065_add_udi_outliers_threshold.sql

ALTER TABLE udi_outliers
    DROP COLUMN IF EXISTS threshold;
