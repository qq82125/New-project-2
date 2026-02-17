-- Add field_diffs (SSOT: docs/nmpa_field_dictionary_v1_adapted.yaml)
-- Constraints:
-- - No rename/delete/type change on existing schema.
-- - Idempotent (IF NOT EXISTS).
-- - Reversible via scripts/rollback/0020_add_field_diffs_down.sql

CREATE TABLE IF NOT EXISTS field_diffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES nmpa_snapshots(id),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    field_name TEXT NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    change_type VARCHAR(20) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_field_diffs_registration_id
    ON field_diffs (registration_id);

CREATE INDEX IF NOT EXISTS idx_field_diffs_field_name
    ON field_diffs (field_name);

CREATE INDEX IF NOT EXISTS idx_field_diffs_source_run_id
    ON field_diffs (source_run_id);

