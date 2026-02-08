CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    country VARCHAR(80),
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_no VARCHAR(120) NOT NULL UNIQUE,
    filing_no VARCHAR(120),
    approval_date DATE,
    expiry_date DATE,
    status VARCHAR(50),
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    udi_di VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(500) NOT NULL,
    model VARCHAR(255),
    specification VARCHAR(255),
    category VARCHAR(120),
    company_id UUID REFERENCES companies(id),
    registration_id UUID REFERENCES registrations(id),
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    package_name VARCHAR(255),
    package_md5 VARCHAR(64),
    download_url TEXT,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    records_total INTEGER NOT NULL DEFAULT 0,
    records_success INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS change_log (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(30) NOT NULL,
    entity_id UUID NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    changed_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    before_json JSONB,
    after_json JSONB,
    source_run_id BIGINT REFERENCES source_runs(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_name_tsv ON products
USING GIN (to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(model, '') || ' ' || coalesce(specification, '')));

CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_companies_name_trgm ON companies USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_source_runs_started_at ON source_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_entity ON change_log(entity_type, entity_id);
