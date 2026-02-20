DROP INDEX IF EXISTS idx_raw_documents_archive_status_fetched_at;
DROP INDEX IF EXISTS idx_raw_source_records_archive_status_observed_at;

ALTER TABLE raw_documents DROP COLUMN IF EXISTS archive_status;
ALTER TABLE raw_documents DROP COLUMN IF EXISTS archived_at;
ALTER TABLE raw_documents DROP COLUMN IF EXISTS archive_note;

ALTER TABLE raw_source_records DROP COLUMN IF EXISTS archive_status;
ALTER TABLE raw_source_records DROP COLUMN IF EXISTS archived_at;
ALTER TABLE raw_source_records DROP COLUMN IF EXISTS archive_note;
