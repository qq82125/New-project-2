-- Rollback for 0063_add_product_variants_registry_no_di_unique.sql

DROP INDEX IF EXISTS uq_product_variants_registry_no_di;
