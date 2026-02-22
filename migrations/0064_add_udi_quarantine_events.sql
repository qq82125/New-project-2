-- 0064: dedicated table for UDI quarantine/isolation events.

CREATE TABLE IF NOT EXISTS udi_quarantine_events (
    id BIGSERIAL PRIMARY KEY,
    source_run_id BIGINT NULL,
    event_type TEXT NOT NULL,
    reg_no TEXT NULL,
    di TEXT NULL,
    count INT NOT NULL DEFAULT 1,
    details JSONB NULL,
    message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_udi_quarantine_events_source_run_id
    ON udi_quarantine_events (source_run_id);

CREATE INDEX IF NOT EXISTS idx_udi_quarantine_events_event_type
    ON udi_quarantine_events (event_type);

CREATE INDEX IF NOT EXISTS idx_udi_quarantine_events_reg_no
    ON udi_quarantine_events (reg_no);

CREATE INDEX IF NOT EXISTS idx_udi_quarantine_events_di
    ON udi_quarantine_events (di);
