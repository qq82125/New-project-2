-- Raw data retention lifecycle metadata and archive scan indexes.
-- Rollback: scripts/rollback/0055_add_raw_archive_lifecycle_down.sql

ALTER TABLE raw_documents
    ADD COLUMN IF NOT EXISTS archive_status VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE raw_documents
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
ALTER TABLE raw_documents
    ADD COLUMN IF NOT EXISTS archive_note TEXT NULL;

ALTER TABLE raw_source_records
    ADD COLUMN IF NOT EXISTS archive_status VARCHAR(20) NOT NULL DEFAULT 'active';
ALTER TABLE raw_source_records
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;
ALTER TABLE raw_source_records
    ADD COLUMN IF NOT EXISTS archive_note TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_raw_documents_archive_status_fetched_at
    ON raw_documents (archive_status, fetched_at);
CREATE INDEX IF NOT EXISTS idx_raw_source_records_archive_status_observed_at
    ON raw_source_records (archive_status, observed_at);
