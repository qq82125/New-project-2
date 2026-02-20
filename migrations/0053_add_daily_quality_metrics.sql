-- Daily data quality metrics (key-value with structured meta).
-- Rollback: scripts/rollback/0053_add_daily_quality_metrics_down.sql

CREATE TABLE IF NOT EXISTS daily_quality_metrics (
    date DATE NOT NULL,
    key TEXT NOT NULL,
    value NUMERIC(14,6) NOT NULL DEFAULT 0,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (date, key)
);

CREATE INDEX IF NOT EXISTS idx_daily_quality_metrics_date
    ON daily_quality_metrics (date);
CREATE INDEX IF NOT EXISTS idx_daily_quality_metrics_key
    ON daily_quality_metrics (key);
