-- Rollback for migrations/0014_pri5_ivd_subtypes.sql

DROP INDEX IF EXISTS idx_products_ivd_subtypes;

ALTER TABLE IF EXISTS products_archive
    DROP COLUMN IF EXISTS ivd_subtypes;

ALTER TABLE IF EXISTS products
    DROP COLUMN IF EXISTS ivd_subtypes;
