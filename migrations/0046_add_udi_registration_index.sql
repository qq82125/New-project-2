-- 0046: UDI registration index (read-optimized aggregation over udi_device_index).
-- Purpose:
-- - Provide a fast, stable count of unique registration_no_norm and DI coverage per registration.
-- - Used by the standardized UDI full import runbook for SQL acceptance checks.
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS udi_registration_index (
    registration_no_norm VARCHAR(120) PRIMARY KEY,
    di_count BIGINT NOT NULL DEFAULT 0,
    has_cert_yes BOOLEAN NOT NULL DEFAULT FALSE,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Backward compatible adds.
ALTER TABLE udi_registration_index ADD COLUMN IF NOT EXISTS di_count BIGINT;
ALTER TABLE udi_registration_index ADD COLUMN IF NOT EXISTS has_cert_yes BOOLEAN;
ALTER TABLE udi_registration_index ADD COLUMN IF NOT EXISTS source_run_id BIGINT;
ALTER TABLE udi_registration_index ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_udi_registration_index_source_run_id
    ON udi_registration_index (source_run_id);

CREATE INDEX IF NOT EXISTS idx_udi_registration_index_di_count
    ON udi_registration_index (di_count);

