-- Add pending_documents queue (canonical key missing document-level backlog)
--
-- Contract:
-- - pending_documents stores RawDocument IDs whose payload could not be anchored to canonical key (registration_no).
-- - It is additive and must be idempotent.
-- - It does NOT replace pending_records; pending_records remains the row-level queue.
--
-- Status lifecycle (minimal): pending -> resolved / ignored
-- Note: Keep status values lowercase for consistency with pending_records.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS pending_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    reason_code VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pending_documents_status
        CHECK (status IN ('pending', 'resolved', 'ignored'))
);

-- Required unique: raw_document_id
CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_documents_raw_document_id
    ON pending_documents(raw_document_id);

-- Indexes for backlog views
CREATE INDEX IF NOT EXISTS idx_pending_documents_status
    ON pending_documents(status);
CREATE INDEX IF NOT EXISTS idx_pending_documents_source_run_id
    ON pending_documents(source_run_id);

