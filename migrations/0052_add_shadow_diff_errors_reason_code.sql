-- Structured shadow diff failures for replay/triage.
-- Adds explicit reason_code taxonomy for statistics and operations.

CREATE TABLE IF NOT EXISTS shadow_diff_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id UUID NULL REFERENCES raw_documents(id),
    raw_source_record_id UUID NULL REFERENCES raw_source_records(id),
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    registration_no VARCHAR(120) NULL,
    reason_code TEXT NOT NULL DEFAULT 'UNKNOWN',
    error TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_shadow_diff_errors_reason_code
        CHECK (reason_code IN ('FIELD_MISSING', 'TYPE_MISMATCH', 'VALUE_TOO_LONG', 'PARSE_ERROR', 'UNKNOWN'))
);

CREATE INDEX IF NOT EXISTS idx_shadow_diff_errors_source_run_id
    ON shadow_diff_errors (source_run_id);
CREATE INDEX IF NOT EXISTS idx_shadow_diff_errors_reason_code
    ON shadow_diff_errors (reason_code);
CREATE INDEX IF NOT EXISTS idx_shadow_diff_errors_raw_document_id
    ON shadow_diff_errors (raw_document_id);
CREATE INDEX IF NOT EXISTS idx_shadow_diff_errors_raw_source_record_id
    ON shadow_diff_errors (raw_source_record_id);
CREATE INDEX IF NOT EXISTS idx_shadow_diff_errors_created_at
    ON shadow_diff_errors (created_at DESC);
