-- Source Contract: registration conflict decision audit (applied/rejected).
-- Additive and idempotent.

CREATE TABLE IF NOT EXISTS registration_conflict_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    registration_no VARCHAR(120) NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT NULL,
    incoming_value TEXT NULL,
    final_value TEXT NULL,
    resolution VARCHAR(20) NOT NULL, -- APPLIED / REJECTED
    reason TEXT NULL,
    existing_meta JSONB NULL,
    incoming_meta JSONB NULL,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registration_conflict_audit_registration_no
    ON registration_conflict_audit (registration_no);
CREATE INDEX IF NOT EXISTS idx_registration_conflict_audit_registration_id
    ON registration_conflict_audit (registration_id);
CREATE INDEX IF NOT EXISTS idx_registration_conflict_audit_created_at
    ON registration_conflict_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_registration_conflict_audit_resolution
    ON registration_conflict_audit (resolution);
CREATE INDEX IF NOT EXISTS idx_registration_conflict_audit_field_name
    ON registration_conflict_audit (field_name);

