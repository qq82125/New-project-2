-- Add import summary metrics (parse level/reason distribution) for offline datasets.
-- Rollback: scripts/rollback/0058_offline_datasets_add_summary_json_down.sql

ALTER TABLE offline_datasets
    ADD COLUMN IF NOT EXISTS summary_json JSONB NOT NULL DEFAULT '{}'::jsonb;
