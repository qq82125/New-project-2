DROP INDEX IF EXISTS idx_offline_dataset_files_source_relpath;
DROP INDEX IF EXISTS idx_offline_dataset_files_source_sha_imported;
DROP INDEX IF EXISTS idx_offline_dataset_files_dataset;
DROP INDEX IF EXISTS idx_offline_datasets_dataset_version;
DROP INDEX IF EXISTS idx_offline_datasets_source_created;

DROP TABLE IF EXISTS offline_dataset_files;
DROP TABLE IF EXISTS offline_datasets;
