-- PR-I1: IVD model fields + cleanup run audit table
-- Idempotent migration: safe to execute repeatedly.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS is_ivd BOOLEAN;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ivd_category TEXT;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ivd_reason JSONB;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ivd_version INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_products_is_ivd ON products (is_ivd);
CREATE INDEX IF NOT EXISTS idx_products_ivd_category ON products (ivd_category);

CREATE TABLE IF NOT EXISTS data_cleanup_runs (
    id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    archived_count INTEGER NOT NULL DEFAULT 0,
    deleted_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_cleanup_runs_run_at ON data_cleanup_runs (run_at DESC);
