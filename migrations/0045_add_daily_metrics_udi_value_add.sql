-- 0045: daily_metrics UDI value-add metrics (coverage + enrichment visibility)
-- Idempotent: safe to run multiple times.
-- Rollback: scripts/rollback/0045_add_daily_metrics_udi_value_add_down.sql

ALTER TABLE daily_metrics
    ADD COLUMN IF NOT EXISTS udi_metrics JSONB NOT NULL DEFAULT '{}'::jsonb;

