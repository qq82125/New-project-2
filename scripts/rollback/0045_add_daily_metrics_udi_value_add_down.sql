-- Rollback for 0045_add_daily_metrics_udi_value_add.sql
ALTER TABLE daily_metrics
    DROP COLUMN IF EXISTS udi_metrics;

