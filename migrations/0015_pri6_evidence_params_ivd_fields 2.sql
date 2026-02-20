-- PR-I6: evidence chain, params tables, and stricter IVD metadata fields.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ivd_source VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS ivd_confidence NUMERIC(3,2) NULL;

ALTER TABLE products_archive
    ADD COLUMN IF NOT EXISTS archive_batch_id VARCHAR(120) NULL;

CREATE INDEX IF NOT EXISTS idx_products_archive_batch_id ON products_archive (archive_batch_id);
CREATE INDEX IF NOT EXISTS idx_products_ivd_source ON products (ivd_source);

ALTER TABLE products
    DROP CONSTRAINT IF EXISTS ck_products_ivd_category_required;

ALTER TABLE products
    ADD CONSTRAINT ck_products_ivd_category_required
    CHECK (is_ivd IS NOT TRUE OR ivd_category IS NOT NULL);

CREATE TABLE IF NOT EXISTS raw_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(40) NOT NULL,
    source_url TEXT NULL,
    doc_type VARCHAR(20) NULL,
    storage_uri TEXT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_id VARCHAR(120) NOT NULL,
    parse_status VARCHAR(20) NULL,
    parse_log JSONB NULL,
    error TEXT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_documents_source_run_sha
    ON raw_documents (source, run_id, sha256);
CREATE INDEX IF NOT EXISTS idx_raw_documents_source ON raw_documents (source);
CREATE INDEX IF NOT EXISTS idx_raw_documents_run_id ON raw_documents (run_id);

CREATE TABLE IF NOT EXISTS product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    di VARCHAR(128) NOT NULL UNIQUE,
    registry_no VARCHAR(120) NULL,
    product_id UUID NULL REFERENCES products(id),
    product_name TEXT NULL,
    model_spec TEXT NULL,
    packaging TEXT NULL,
    manufacturer TEXT NULL,
    is_ivd BOOLEAN NOT NULL DEFAULT FALSE,
    ivd_category VARCHAR(20) NULL,
    ivd_version VARCHAR(40) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_variants_registry_no ON product_variants (registry_no);
CREATE INDEX IF NOT EXISTS idx_product_variants_is_ivd ON product_variants (is_ivd);
CREATE INDEX IF NOT EXISTS idx_product_variants_ivd_category ON product_variants (ivd_category);

CREATE TABLE IF NOT EXISTS product_params (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    di VARCHAR(128) NULL,
    registry_no VARCHAR(120) NULL,
    param_code VARCHAR(80) NOT NULL,
    value_num NUMERIC(18,6) NULL,
    value_text TEXT NULL,
    unit VARCHAR(50) NULL,
    range_low NUMERIC(18,6) NULL,
    range_high NUMERIC(18,6) NULL,
    conditions JSONB NULL,
    evidence_text TEXT NOT NULL,
    evidence_page INTEGER NULL,
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    extract_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_params_di_code ON product_params (di, param_code);
CREATE INDEX IF NOT EXISTS idx_product_params_regno_code ON product_params (registry_no, param_code);
CREATE INDEX IF NOT EXISTS idx_product_params_raw_document_id ON product_params (raw_document_id);

CREATE TABLE IF NOT EXISTS products_rejected (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(40) NULL,
    source_key VARCHAR(255) NULL,
    raw_document_id UUID NULL REFERENCES raw_documents(id),
    reason JSONB NULL,
    ivd_version VARCHAR(40) NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_rejected_source_key ON products_rejected (source_key);
CREATE INDEX IF NOT EXISTS idx_products_rejected_rejected_at ON products_rejected (rejected_at DESC);

CREATE TABLE IF NOT EXISTS nhsa_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    month VARCHAR(7) NULL,
    code VARCHAR(120) NOT NULL UNIQUE,
    name TEXT NULL,
    specification TEXT NULL,
    manufacturer TEXT NULL,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Legacy bootstrap table in this migration uses `month`; 0017 migrates it to `snapshot_month`.
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_month ON nhsa_codes (month);
