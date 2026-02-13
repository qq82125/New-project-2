-- Rollback for migrations/0013_pri4_products_archive.sql

DROP INDEX IF EXISTS idx_products_archive_cleanup_run_id;
DROP INDEX IF EXISTS idx_products_archive_archived_at;
DROP INDEX IF EXISTS idx_products_archive_udi_di;
DROP INDEX IF EXISTS idx_products_archive_product_id;
DROP TABLE IF EXISTS products_archive;
