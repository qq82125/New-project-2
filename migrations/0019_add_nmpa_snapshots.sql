-- Add nmpa_snapshots (SSOT: docs/nmpa_field_dictionary_v1_adapted.yaml)
-- Constraints:
-- - No rename/delete/type change on existing schema.
-- - Idempotent (IF NOT EXISTS).
-- - Reversible via scripts/rollback/0019_add_nmpa_snapshots_down.sql

CREATE TABLE IF NOT EXISTS nmpa_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    raw_document_id UUID NULL REFERENCES raw_documents(id),
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    snapshot_date DATE NOT NULL,
    source_url TEXT NULL,
    sha256 VARCHAR(64) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nmpa_snapshots_registration_source_run
    ON nmpa_snapshots (registration_id, source_run_id);

CREATE INDEX IF NOT EXISTS idx_nmpa_snapshots_registration_id
    ON nmpa_snapshots (registration_id);

CREATE INDEX IF NOT EXISTS idx_nmpa_snapshots_snapshot_date
    ON nmpa_snapshots (snapshot_date);

CREATE INDEX IF NOT EXISTS idx_nmpa_snapshots_source_run_id
    ON nmpa_snapshots (source_run_id);

