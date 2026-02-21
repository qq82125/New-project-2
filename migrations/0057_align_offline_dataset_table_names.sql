-- Align to contract tables:
-- offline_datasets / offline_dataset_files
-- Compatible with environments that already have offline_import_datasets/files.
-- Rollback: scripts/rollback/0057_align_offline_dataset_table_names_down.sql

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

CREATE INDEX IF NOT EXISTS idx_offline_datasets_source_created
    ON offline_datasets (source_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_offline_datasets_dataset_version
    ON offline_datasets (dataset_version);
CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_dataset
    ON offline_dataset_files (dataset_id);
CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_source_sha_imported
    ON offline_dataset_files (source_key, file_sha256, imported);
CREATE INDEX IF NOT EXISTS idx_offline_dataset_files_source_relpath
    ON offline_dataset_files (source_key, relative_path);

-- Backfill from legacy table names if present and target rows missing.
INSERT INTO offline_datasets (
    source_key, dataset_version, root_path, recursive, max_depth, pattern,
    files_scanned, files_imported, files_skipped, rows_written, rows_failed,
    dry_run, started_at, finished_at, created_at
)
SELECT
    COALESCE(NULLIF(oid.source, ''), 'nmpa_legacy_dump') AS source_key,
    oid.dataset_version,
    oid.root_path,
    COALESCE(oid.scan_recursive, TRUE) AS recursive,
    COALESCE(oid.max_depth, 0) AS max_depth,
    '*.csv,*.xlsx,*.xls,*.json,*.ndjson' AS pattern,
    COALESCE(oid.files_scanned, 0) AS files_scanned,
    COALESCE(oid.files_new, 0) AS files_imported,
    COALESCE(oid.files_duplicate, 0) AS files_skipped,
    COALESCE(oid.rows_written, 0) AS rows_written,
    0 AS rows_failed,
    FALSE AS dry_run,
    COALESCE(oid.created_at, NOW()) AS started_at,
    oid.updated_at AS finished_at,
    COALESCE(oid.created_at, NOW()) AS created_at
FROM offline_import_datasets oid
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'offline_import_datasets'
)
  AND NOT EXISTS (
    SELECT 1 FROM offline_datasets od
    WHERE od.source_key = COALESCE(NULLIF(oid.source, ''), 'nmpa_legacy_dump')
      AND od.dataset_version = oid.dataset_version
  );

INSERT INTO offline_dataset_files (
    dataset_id, source_key, storage_uri, relative_path, file_sha256, file_size, file_mtime,
    imported, skipped_reason, rows_scanned, rows_written, rows_failed
)
SELECT
    od.id AS dataset_id,
    od.source_key,
    oif.storage_uri,
    oif.relative_path,
    oif.file_sha256,
    COALESCE(oif.file_size, 0),
    COALESCE(oif.file_mtime, NOW()),
    COALESCE(oif.is_new_file, FALSE) AS imported,
    CASE WHEN COALESCE(oif.is_new_file, FALSE) THEN NULL ELSE 'DUP_SHA256' END AS skipped_reason,
    COALESCE(oif.row_count, 0) AS rows_scanned,
    COALESCE(oif.rows_written, 0) AS rows_written,
    0 AS rows_failed
FROM offline_import_files oif
JOIN offline_datasets od
  ON od.dataset_version = oif.dataset_version
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'offline_import_files'
)
  AND NOT EXISTS (
    SELECT 1
    FROM offline_dataset_files n
    WHERE n.dataset_id = od.id
      AND n.file_sha256 = oif.file_sha256
      AND n.relative_path = oif.relative_path
  );
