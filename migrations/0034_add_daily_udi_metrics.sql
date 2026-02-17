-- Daily UDI coverage snapshot metrics.
-- This migration is additive and idempotent.

CREATE TABLE IF NOT EXISTS daily_udi_metrics (
    metric_date DATE PRIMARY KEY,
    total_di_count INTEGER NOT NULL DEFAULT 0,
    mapped_di_count INTEGER NOT NULL DEFAULT 0,
    unmapped_di_count INTEGER NOT NULL DEFAULT 0,
    coverage_ratio NUMERIC(8,6) NOT NULL DEFAULT 0,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_udi_metrics_source_run_id
    ON daily_udi_metrics (source_run_id);

