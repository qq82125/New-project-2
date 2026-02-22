-- Rollback for 0061_add_products_soft_dedupe_columns.sql

ALTER TABLE products
    DROP CONSTRAINT IF EXISTS fk_products_superseded_by;

DROP INDEX IF EXISTS idx_products_superseded_by;
DROP INDEX IF EXISTS idx_products_is_hidden;

ALTER TABLE products
    DROP COLUMN IF EXISTS is_hidden;

ALTER TABLE products
    DROP COLUMN IF EXISTS superseded_by;
