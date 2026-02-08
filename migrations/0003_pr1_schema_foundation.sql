-- PR1: Database schema foundation for NMPA IVD intelligence dashboard
-- PostgreSQL 15+

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) companies
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    country VARCHAR(80),
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE companies ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb;

-- 2) products
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    name VARCHAR(500) NOT NULL,
    reg_no VARCHAR(120),
    udi_di VARCHAR(128) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    approved_date DATE,
    expiry_date DATE,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE products ADD COLUMN IF NOT EXISTS company_id UUID;
ALTER TABLE products ADD COLUMN IF NOT EXISTS reg_no VARCHAR(120);
ALTER TABLE products ADD COLUMN IF NOT EXISTS udi_di VARCHAR(128);
ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE products ADD COLUMN IF NOT EXISTS approved_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb;

-- 3) source_runs
CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    run_type VARCHAR(30) NOT NULL DEFAULT 'INGEST',
    status VARCHAR(20) NOT NULL,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS run_type VARCHAR(30) NOT NULL DEFAULT 'INGEST';
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 4) change_log
CREATE TABLE IF NOT EXISTS change_log (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    source_run_id BIGINT REFERENCES source_runs(id),
    change_type VARCHAR(20) NOT NULL,
    changed_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    before_raw JSONB,
    after_raw JSONB,
    change_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE change_log ADD COLUMN IF NOT EXISTS product_id UUID;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS change_type VARCHAR(20);
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS changed_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS before_raw JSONB;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS after_raw JSONB;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS change_date TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 5) subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    subscription_type VARCHAR(30) NOT NULL,
    target_value VARCHAR(255) NOT NULL,
    webhook_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_digest_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS company_id UUID;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS subscription_type VARCHAR(30);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS target_value VARCHAR(255);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS webhook_url TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_digest_date DATE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 6) daily_metrics (one row per day)
CREATE TABLE IF NOT EXISTS daily_metrics (
    metric_date DATE PRIMARY KEY,
    new_products INTEGER NOT NULL DEFAULT 0,
    updated_products INTEGER NOT NULL DEFAULT 0,
    cancelled_products INTEGER NOT NULL DEFAULT 0,
    expiring_in_90d INTEGER NOT NULL DEFAULT 0,
    active_subscriptions INTEGER NOT NULL DEFAULT 0,
    source_run_id BIGINT REFERENCES source_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Search indexes (fuzzy + full-text)
CREATE INDEX IF NOT EXISTS idx_companies_name_trgm ON companies USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_reg_no_trgm ON products USING GIN (reg_no gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_udi_di_trgm ON products USING GIN (udi_di gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_products_search_tsv ON products
USING GIN (to_tsvector('simple', COALESCE(name, '') || ' ' || COALESCE(reg_no, '') || ' ' || COALESCE(udi_di, '')));

-- Dashboard/query indexes
CREATE INDEX IF NOT EXISTS idx_products_company_id ON products(company_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_approved_date ON products(approved_date);
CREATE INDEX IF NOT EXISTS idx_products_expiry_date ON products(expiry_date);

CREATE INDEX IF NOT EXISTS idx_change_log_product_date ON change_log(product_id, change_date DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_type_date ON change_log(change_type, change_date DESC);
CREATE INDEX IF NOT EXISTS idx_source_runs_status_time ON source_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_subscriptions_type_target ON subscriptions(subscription_type, target_value);

-- Daily metrics date key lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_metrics_metric_date ON daily_metrics(metric_date);
