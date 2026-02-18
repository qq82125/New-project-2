-- Time Engine V1: extend registration_events schema for business event chain consumption.
--
-- Notes:
-- - registration_events table already exists (0025_add_registration_events.sql).
-- - This migration is additive: it only adds columns and indexes, without changing existing semantics.
-- - New CLI derives events from field_diffs (and registration creation) into this table.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS event_seq INTEGER NULL;

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS effective_from DATE NULL;

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS effective_to DATE NULL;

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS raw_document_id UUID NULL REFERENCES raw_documents(id);

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS diff_json JSONB NULL;

ALTER TABLE registration_events
    ADD COLUMN IF NOT EXISTS notes TEXT NULL;

-- Keep (registration_id, event_seq) unique when event_seq is populated.
CREATE UNIQUE INDEX IF NOT EXISTS uq_registration_events_reg_seq
    ON registration_events (registration_id, event_seq)
    WHERE event_seq IS NOT NULL;

-- Additional indexes for Time Engine reads
CREATE INDEX IF NOT EXISTS idx_registration_events_event_type
    ON registration_events (event_type);

CREATE INDEX IF NOT EXISTS idx_registration_events_observed_at
    ON registration_events (observed_at);

