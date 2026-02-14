-- PR-I7: archive table for change_log rows when cleaning up non-IVD products.
-- Idempotent migration.

CREATE TABLE IF NOT EXISTS change_log_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    id BIGINT NULL,
    product_id UUID NULL,
    entity_type VARCHAR(30) NULL,
    entity_id UUID NULL,
    change_type VARCHAR(20) NULL,
    changed_fields JSONB NULL,
    before_json JSONB NULL,
    after_json JSONB NULL,
    before_raw JSONB NULL,
    after_raw JSONB NULL,
    source_run_id BIGINT NULL,
    changed_at TIMESTAMPTZ NULL,
    change_date TIMESTAMPTZ NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cleanup_run_id BIGINT NULL,
    archive_batch_id VARCHAR(120) NULL,
    archive_reason TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_change_log_archive_product_id ON change_log_archive (product_id);
CREATE INDEX IF NOT EXISTS idx_change_log_archive_entity ON change_log_archive (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_change_log_archive_archived_at ON change_log_archive (archived_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_archive_cleanup_run_id ON change_log_archive (cleanup_run_id);
CREATE INDEX IF NOT EXISTS idx_change_log_archive_batch_id ON change_log_archive (archive_batch_id);
