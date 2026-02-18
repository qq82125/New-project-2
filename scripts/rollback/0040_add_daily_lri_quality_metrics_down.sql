-- Rollback for migrations/0040_add_daily_lri_quality_metrics.sql

ALTER TABLE daily_metrics DROP COLUMN IF EXISTS risk_level_distribution;
ALTER TABLE daily_metrics DROP COLUMN IF EXISTS lri_missing_methodology_count;
ALTER TABLE daily_metrics DROP COLUMN IF EXISTS lri_computed_count;
ALTER TABLE daily_metrics DROP COLUMN IF EXISTS pending_count;

