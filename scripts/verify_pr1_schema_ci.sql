-- PR1 checklist verifier (CI-friendly output)
-- Output format per check: CHECKLIST_<n>_<name>=PASS|FAIL
-- Fails with non-zero exit code when any checklist fails.

BEGIN;

CREATE TEMP TABLE _check_results (
    check_key text PRIMARY KEY,
    passed boolean NOT NULL,
    detail text
) ON COMMIT DROP;

-- 1) required tables exist
INSERT INTO _check_results(check_key, passed, detail)
SELECT
    'CHECKLIST_1_TABLES_EXIST',
    (missing_count = 0),
    CASE WHEN missing_count = 0 THEN 'all required tables exist'
         ELSE format('missing_count=%s', missing_count)
    END
FROM (
    SELECT COUNT(*) AS missing_count
    FROM (
        VALUES ('companies'), ('products'), ('change_log'), ('source_runs'), ('subscriptions'), ('daily_metrics')
    ) AS req(tbl)
    LEFT JOIN pg_class c ON c.relname = req.tbl AND c.relkind = 'r'
    LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.oid IS NULL OR n.nspname <> current_schema()
) s;

-- 2) foreign keys are correct
INSERT INTO _check_results(check_key, passed, detail)
SELECT
    'CHECKLIST_2_FOREIGN_KEYS',
    (fk_count = 5),
    format('expected=5 actual=%s', fk_count)
FROM (
    WITH expected AS (
        SELECT 'products'::text AS tbl, 'company_id'::text AS col, 'companies'::text AS ref_tbl
        UNION ALL SELECT 'change_log', 'product_id', 'products'
        UNION ALL SELECT 'change_log', 'source_run_id', 'source_runs'
        UNION ALL SELECT 'subscriptions', 'company_id', 'companies'
        UNION ALL SELECT 'daily_metrics', 'source_run_id', 'source_runs'
    )
    SELECT COUNT(*) AS fk_count
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
     AND ccu.table_name = e.ref_tbl
) s;

-- 3) fuzzy search indexes (pg_trgm + products/companies trigram)
INSERT INTO _check_results(check_key, passed, detail)
SELECT
    'CHECKLIST_3_FUZZY_INDEXES',
    (has_pg_trgm AND trigram_idx_count >= 2),
    format('pg_trgm=%s trigram_idx_count=%s', has_pg_trgm, trigram_idx_count)
FROM (
    SELECT
        EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') AS has_pg_trgm,
        (
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND (
                    indexdef ILIKE '% ON companies % gin %name%gin_trgm_ops%'
                 OR indexdef ILIKE '% ON products % gin %name%gin_trgm_ops%'
              )
        ) AS trigram_idx_count
) s;

-- 4) daily_metrics is one-row-per-day via date primary key
INSERT INTO _check_results(check_key, passed, detail)
SELECT
    'CHECKLIST_4_DAILY_METRICS_PK',
    has_pk_on_date,
    CASE WHEN has_pk_on_date THEN 'daily_metrics.metric_date is primary key'
         ELSE 'daily_metrics.metric_date primary key missing'
    END
FROM (
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
    ) AS has_pk_on_date
) s;

-- 5) migration idempotency smoke check (core IF NOT EXISTS statements)
DO $$
BEGIN
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

    INSERT INTO _check_results(check_key, passed, detail)
    VALUES ('CHECKLIST_5_IDEMPOTENT_MIGRATION', true, 'idempotent statements re-executed successfully');
EXCEPTION WHEN OTHERS THEN
    INSERT INTO _check_results(check_key, passed, detail)
    VALUES ('CHECKLIST_5_IDEMPOTENT_MIGRATION', false, SQLERRM);
END $$;

-- CI-readable output lines
SELECT check_key || '=' || CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END || ' detail=' || detail AS ci_line
FROM _check_results
ORDER BY check_key;

DO $$
DECLARE
    fail_count integer;
BEGIN
    SELECT COUNT(*) INTO fail_count FROM _check_results WHERE passed = false;
    IF fail_count > 0 THEN
        RAISE EXCEPTION 'PR1 checklist failed: % check(s) failed', fail_count;
    END IF;
END $$;

ROLLBACK;
