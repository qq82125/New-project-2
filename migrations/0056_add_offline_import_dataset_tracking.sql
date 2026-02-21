-- Recursive + versioned offline import metadata tables.
-- Rollback: scripts/rollback/0056_add_offline_import_dataset_tracking_down.sql

CREATE TABLE IF NOT EXISTS offline_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    root_path TEXT NOT NULL,
    recursive BOOLEAN NOT NULL DEFAULT TRUE,
    max_depth INTEGER NOT NULL DEFAULT 0,
    pattern TEXT NOT NULL,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    files_imported INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    rows_written INTEGER NOT NULL DEFAULT 0,
    rows_failed INTEGER NOT NULL DEFAULT 0,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_key, dataset_version)
);

CREATE INDEX IF NOT EXISTS idx_offline_datasets_source_created
    ON offline_datasets (source_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_offline_datasets_dataset_version
    ON offline_datasets (dataset_version);

CREATE TABLE IF NOT EXISTS offline_dataset_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES offline_datasets(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_sha256 VARCHAR(64) NOT NULL,
    file_size BIGINT NOT NULL,
    file_mtime TIMESTAMPTZ NOT NULL,
    imported BOOLEAN NOT NULL DEFAULT FALSE,
    skipped_reason TEXT NULL,
    rows_scanned INTEGER NOT NULL DEFAULT 0,
    rows_written INTEGER NOT NULL DEFAULT 0,
    rows_failed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_dataset
    ON offline_dataset_files (dataset_id);
CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_source_sha_imported
    ON offline_dataset_files (source_key, file_sha256, imported);
CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_source_relpath
    ON offline_dataset_files (source_key, relative_path);
