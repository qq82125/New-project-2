-- Registration anchor enforcement: unresolved records queue for ingest runner.
-- Additive and idempotent.

CREATE TABLE IF NOT EXISTS pending_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(80) NOT NULL,
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    payload_hash VARCHAR(64) NOT NULL,
    registration_no_raw TEXT NULL,
    reason_code VARCHAR(50) NOT NULL,
    reason TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pending_records_status CHECK (status IN ('pending', 'resolved', 'ignored')),
    CONSTRAINT uq_pending_records_run_payload UNIQUE (source_run_id, payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_pending_records_source_key
    ON pending_records (source_key);
CREATE INDEX IF NOT EXISTS idx_pending_records_status
    ON pending_records (status);
CREATE INDEX IF NOT EXISTS idx_pending_records_source_run_id
    ON pending_records (source_run_id);
CREATE INDEX IF NOT EXISTS idx_pending_records_created_at
    ON pending_records (created_at DESC);
