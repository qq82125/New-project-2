-- Add registration_events (version events for productized consumption).
--
-- Must not change existing nmpa_snapshots/field_diffs SSOT.

CREATE TABLE IF NOT EXISTS registration_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    event_type TEXT NOT NULL,
    event_date DATE NOT NULL,
    summary TEXT NULL,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    snapshot_id UUID NULL REFERENCES nmpa_snapshots(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registration_events_registration_id
    ON registration_events (registration_id);

CREATE INDEX IF NOT EXISTS idx_registration_events_event_date
    ON registration_events (event_date);

CREATE INDEX IF NOT EXISTS idx_registration_events_source_run_id
    ON registration_events (source_run_id);

-- Idempotency key: same registration + run + event_type should not duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS uq_registration_events_reg_run_type
    ON registration_events (registration_id, source_run_id, event_type);

