-- Source Contract v1.1: foundational tables for Fetch/Parse/Normalize/Upsert pipeline.
-- Constraints:
-- - Additive only (no rename/delete existing schema objects)
-- - Idempotent DDL

CREATE TABLE IF NOT EXISTS raw_source_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    source_url TEXT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    evidence_grade VARCHAR(1) NOT NULL DEFAULT 'C',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NULL,
    parse_status VARCHAR(20) NULL,
    parse_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_raw_source_records_evidence_grade
        CHECK (evidence_grade IN ('A', 'B', 'C', 'D'))
);

CREATE INDEX IF NOT EXISTS idx_raw_source_records_source
    ON raw_source_records (source);
CREATE INDEX IF NOT EXISTS idx_raw_source_records_source_run_id
    ON raw_source_records (source_run_id);
CREATE INDEX IF NOT EXISTS idx_raw_source_records_observed_at
    ON raw_source_records (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_source_records_parse_status
    ON raw_source_records (parse_status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_source_records_run_payload_hash
    ON raw_source_records (source_run_id, payload_hash);

CREATE TABLE IF NOT EXISTS product_udi_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_no VARCHAR(120) NOT NULL REFERENCES registrations(registration_no),
    di VARCHAR(128) NOT NULL,
    source TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    raw_source_record_id UUID NULL REFERENCES raw_source_records(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_udi_map_registration_no
    ON product_udi_map (registration_no);
CREATE INDEX IF NOT EXISTS idx_product_udi_map_di
    ON product_udi_map (di);
CREATE INDEX IF NOT EXISTS idx_product_udi_map_raw_source_record_id
    ON product_udi_map (raw_source_record_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_udi_map_reg_di
    ON product_udi_map (registration_no, di);

CREATE TABLE IF NOT EXISTS udi_di_master (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    di VARCHAR(128) NOT NULL UNIQUE,
    payload_hash VARCHAR(64) NULL,
    source TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_source_record_id UUID NULL REFERENCES raw_source_records(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_udi_di_master_source
    ON udi_di_master (source);
CREATE INDEX IF NOT EXISTS idx_udi_di_master_last_seen_at
    ON udi_di_master (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_udi_di_master_raw_source_record_id
    ON udi_di_master (raw_source_record_id);

CREATE TABLE IF NOT EXISTS pending_udi_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    di VARCHAR(128) NOT NULL REFERENCES udi_di_master(di),
    reason TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    raw_source_record_id UUID NULL REFERENCES raw_source_records(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_udi_links_di
    ON pending_udi_links (di);
CREATE INDEX IF NOT EXISTS idx_pending_udi_links_status
    ON pending_udi_links (status);
CREATE INDEX IF NOT EXISTS idx_pending_udi_links_next_retry_at
    ON pending_udi_links (next_retry_at);
CREATE INDEX IF NOT EXISTS idx_pending_udi_links_raw_source_record_id
    ON pending_udi_links (raw_source_record_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_udi_links_active_di
    ON pending_udi_links (di)
    WHERE status IN ('PENDING', 'RETRYING');

