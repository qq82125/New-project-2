-- PR-I4: archive table for non-IVD cleanup
-- Idempotent migration.

CREATE TABLE IF NOT EXISTS products_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    id UUID NOT NULL,
    udi_di VARCHAR(128) NOT NULL,
    reg_no VARCHAR(120) NULL,
    name VARCHAR(500) NOT NULL,
    class VARCHAR(120) NULL,
    approved_date DATE NULL,
    expiry_date DATE NULL,
    model VARCHAR(255) NULL,
    specification VARCHAR(255) NULL,
    category VARCHAR(120) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    is_ivd BOOLEAN NULL,
    ivd_category TEXT NULL,
    ivd_reason JSONB NULL,
    ivd_version INTEGER NOT NULL DEFAULT 1,
    company_id UUID NULL,
    registration_id UUID NULL,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    cleanup_run_id BIGINT NULL,
    archive_reason TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_archive_product_id ON products_archive (id);
CREATE INDEX IF NOT EXISTS idx_products_archive_udi_di ON products_archive (udi_di);
CREATE INDEX IF NOT EXISTS idx_products_archive_archived_at ON products_archive (archived_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_archive_cleanup_run_id ON products_archive (cleanup_run_id);
