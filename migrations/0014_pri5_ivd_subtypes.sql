-- PR-I5 extension: add ivd_subtypes tags to products and archive table.
-- Idempotent migration.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ivd_subtypes TEXT[] NULL;

ALTER TABLE products_archive
    ADD COLUMN IF NOT EXISTS ivd_subtypes TEXT[] NULL;

CREATE INDEX IF NOT EXISTS idx_products_ivd_subtypes ON products USING GIN (ivd_subtypes);
