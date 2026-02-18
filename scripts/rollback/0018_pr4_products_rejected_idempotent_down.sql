-- Rollback for migrations/0018_pr4_products_rejected_idempotent.sql
--
-- This undoes the idempotency enforcement by dropping the unique index and
-- allowing NULLs again (best-effort).

DROP INDEX IF EXISTS uq_products_rejected_source_key;

ALTER TABLE products_rejected
  ALTER COLUMN source DROP NOT NULL,
  ALTER COLUMN source_key DROP NOT NULL;

