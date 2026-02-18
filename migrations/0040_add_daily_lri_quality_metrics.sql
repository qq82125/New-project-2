-- LRI ops metrics: store LRI run quality indicators on daily_metrics (for ops + digest stability).
--
-- Adds:
-- - pending_count
-- - lri_computed_count
-- - lri_missing_methodology_count
-- - risk_level_distribution (jsonb)
--
-- Idempotent. Rollback: scripts/rollback/0040_add_daily_lri_quality_metrics_down.sql

ALTER TABLE daily_metrics
  ADD COLUMN IF NOT EXISTS pending_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE daily_metrics
  ADD COLUMN IF NOT EXISTS lri_computed_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE daily_metrics
  ADD COLUMN IF NOT EXISTS lri_missing_methodology_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE daily_metrics
  ADD COLUMN IF NOT EXISTS risk_level_distribution JSONB NOT NULL DEFAULT '{}'::jsonb;

