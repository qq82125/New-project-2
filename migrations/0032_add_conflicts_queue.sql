-- Field-level unresolved conflicts queue (manual resolution required).
-- Additive and idempotent; canonical anchor remains registration_no.

CREATE TABLE IF NOT EXISTS conflicts_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_no VARCHAR(120) NOT NULL REFERENCES registrations(registration_no),
    registration_id UUID NULL REFERENCES registrations(id),
    field_name TEXT NOT NULL,
    candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    winner_value TEXT NULL,
    winner_source_key VARCHAR(80) NULL,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    resolved_by TEXT NULL,
    resolved_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conflicts_queue_status
        CHECK (status IN ('open', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_conflicts_queue_status
    ON conflicts_queue (status);
CREATE INDEX IF NOT EXISTS idx_conflicts_queue_registration_no
    ON conflicts_queue (registration_no);
CREATE INDEX IF NOT EXISTS idx_conflicts_queue_field_name
    ON conflicts_queue (field_name);
CREATE INDEX IF NOT EXISTS idx_conflicts_queue_source_run_id
    ON conflicts_queue (source_run_id);
CREATE INDEX IF NOT EXISTS idx_conflicts_queue_created_at
    ON conflicts_queue (created_at DESC);

-- Keep one open queue row for (registration_no, field_name) to reduce noise.
CREATE UNIQUE INDEX IF NOT EXISTS uq_conflicts_queue_open_reg_field
    ON conflicts_queue (registration_no, field_name)
    WHERE status = 'open';
