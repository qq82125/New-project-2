-- Rollback for migrations/0015_pri6_evidence_params_ivd_fields.sql
--
-- IMPORTANT:
-- This migration introduces evidence-chain tables that many later migrations depend on.
-- To execute this rollback cleanly, rollback dependent migrations first (in reverse order).

-- Drop tables introduced by this migration.
DROP TABLE IF EXISTS product_params;
DROP TABLE IF EXISTS product_variants;
DROP TABLE IF EXISTS products_rejected;
DROP TABLE IF EXISTS raw_documents;

-- Drop constraints/indexes introduced by this migration (best-effort).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_ivd_category_required' AND conrelid = 'products'::regclass
  ) THEN
    ALTER TABLE products DROP CONSTRAINT ck_products_ivd_category_required;
  END IF;
END $$;

DROP INDEX IF EXISTS idx_products_archive_batch_id;
DROP INDEX IF EXISTS idx_products_ivd_source;

ALTER TABLE products_archive DROP COLUMN IF EXISTS archive_batch_id;
ALTER TABLE products DROP COLUMN IF EXISTS ivd_source;
ALTER TABLE products DROP COLUMN IF EXISTS ivd_confidence;

