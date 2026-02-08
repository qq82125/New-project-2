-- PR1 checklist verifier (pure SQL, run with psql -f)
-- Target: PostgreSQL 15+

BEGIN;

-- 1) All required tables can be created / exist
DO $$
DECLARE
    missing_count integer;
BEGIN
    SELECT COUNT(*) INTO missing_count
    FROM (
        VALUES
            ('companies'),
            ('products'),
            ('change_log'),
            ('source_runs'),
            ('subscriptions'),
            ('daily_metrics')
    ) AS req(tbl)
    LEFT JOIN pg_class c ON c.relname = req.tbl AND c.relkind = 'r'
    LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.oid IS NULL OR n.nspname <> current_schema();

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Checklist failed: missing required table(s) in schema %', current_schema();
    END IF;
END $$;

-- 2) Foreign key relationships are correct
DO $$
DECLARE
    fk_count integer;
BEGIN
    WITH expected AS (
        SELECT 'products'::text AS tbl, 'company_id'::text AS col, 'companies'::text AS ref_tbl
        UNION ALL SELECT 'change_log', 'product_id', 'products'
        UNION ALL SELECT 'change_log', 'source_run_id', 'source_runs'
        UNION ALL SELECT 'subscriptions', 'company_id', 'companies'
        UNION ALL SELECT 'daily_metrics', 'source_run_id', 'source_runs'
    )
    SELECT COUNT(*) INTO fk_count
    FROM expected e
    JOIN information_schema.key_column_usage kcu
      ON kcu.table_schema = current_schema()
     AND kcu.table_name = e.tbl
     AND kcu.column_name = e.col
    JOIN information_schema.referential_constraints rc
      ON rc.constraint_schema = kcu.constraint_schema
     AND rc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_schema = rc.unique_constraint_schema
     AND ccu.constraint_name = rc.unique_constraint_name
     AND ccu.table_name = e.ref_tbl;

    IF fk_count <> 5 THEN
        RAISE EXCEPTION 'Checklist failed: expected 5 FK mappings, got %', fk_count;
    END IF;
END $$;

-- 3) products / companies fuzzy search indexes (pg_trgm)
DO $$
DECLARE
    has_pg_trgm boolean;
    idx_count integer;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') INTO has_pg_trgm;
    IF NOT has_pg_trgm THEN
        RAISE EXCEPTION 'Checklist failed: extension pg_trgm is not installed';
    END IF;

    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE schemaname = current_schema()
      AND (
            indexdef ILIKE '% ON companies % gin %name%gin_trgm_ops%'
         OR indexdef ILIKE '% ON products % gin %name%gin_trgm_ops%'
      );

    IF idx_count < 2 THEN
        RAISE EXCEPTION 'Checklist failed: missing required trigram indexes for companies/products';
    END IF;
END $$;

-- 4) daily_metrics one-row-per-day (date primary key)
DO $$
DECLARE
    has_pk_on_date boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_schema = kcu.constraint_schema
         AND tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'daily_metrics'
          AND tc.constraint_type = 'PRIMARY KEY'
          AND kcu.column_name = 'metric_date'
    ) INTO has_pk_on_date;

    IF NOT has_pk_on_date THEN
        RAISE EXCEPTION 'Checklist failed: daily_metrics.metric_date is not primary key';
    END IF;
END $$;

-- 5) Migration idempotency (re-run core DDL with IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
-- If any statement is not idempotent, script will error and stop.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    country VARCHAR(80),
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

ALTER TABLE products ADD COLUMN IF NOT EXISTS reg_no VARCHAR(120);
ALTER TABLE products ADD COLUMN IF NOT EXISTS udi_di VARCHAR(128);
ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE products ADD COLUMN IF NOT EXISTS approved_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb;

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

CREATE INDEX IF NOT EXISTS idx_companies_name_trgm ON companies USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_reg_no_trgm ON products USING GIN (reg_no gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_udi_di_trgm ON products USING GIN (udi_di gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_search_tsv ON products
USING GIN (to_tsvector('simple', COALESCE(name, '') || ' ' || COALESCE(reg_no, '') || ' ' || COALESCE(udi_di, '')));

CREATE INDEX IF NOT EXISTS idx_products_company_id ON products(company_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_approved_date ON products(approved_date);
CREATE INDEX IF NOT EXISTS idx_products_expiry_date ON products(expiry_date);
CREATE INDEX IF NOT EXISTS idx_change_log_product_date ON change_log(product_id, change_date DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_type_date ON change_log(change_type, change_date DESC);
CREATE INDEX IF NOT EXISTS idx_source_runs_status_time ON source_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_subscriptions_type_target ON subscriptions(subscription_type, target_value);
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_metrics_metric_date ON daily_metrics(metric_date);

DO $$
BEGIN
    RAISE NOTICE 'PR1 checklist passed for schema: %', current_schema();
END $$;

ROLLBACK;
