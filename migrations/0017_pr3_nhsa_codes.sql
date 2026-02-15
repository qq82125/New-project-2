-- PR3.1: NHSA monthly snapshot ingestion (evidence-chain backed).

-- Historical note:
-- Some environments already have a legacy nhsa_codes table (columns: month/specification, unique(code)).
-- This migration upgrades it in-place to the new schema (snapshot_month/spec, unique(code,snapshot_month)).

CREATE TABLE IF NOT EXISTS nhsa_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL,
    snapshot_month VARCHAR(7) NOT NULL, -- YYYY-MM
    name TEXT NULL,
    spec TEXT NULL,
    manufacturer TEXT NULL,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Column renames for legacy schema.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'nhsa_codes' AND column_name = 'month'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'nhsa_codes' AND column_name = 'snapshot_month'
    ) THEN
        ALTER TABLE nhsa_codes RENAME COLUMN month TO snapshot_month;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'nhsa_codes' AND column_name = 'specification'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'nhsa_codes' AND column_name = 'spec'
    ) THEN
        ALTER TABLE nhsa_codes RENAME COLUMN specification TO spec;
    END IF;
END $$;

-- Ensure required columns exist after legacy upgrades.
ALTER TABLE nhsa_codes
    ADD COLUMN IF NOT EXISTS snapshot_month VARCHAR(7) NULL,
    ADD COLUMN IF NOT EXISTS spec TEXT NULL,
    ADD COLUMN IF NOT EXISTS raw_document_id UUID NULL REFERENCES raw_documents(id),
    ADD COLUMN IF NOT EXISTS source_run_id BIGINT NULL REFERENCES source_runs(id);

-- If the table existed without snapshot_month, backfill and enforce NOT NULL.
UPDATE nhsa_codes SET snapshot_month = '1970-01' WHERE snapshot_month IS NULL;
ALTER TABLE nhsa_codes ALTER COLUMN snapshot_month SET NOT NULL;

-- If the table existed before evidence-chain fields, allow legacy rows to remain NULL but
-- future inserts will always set these; operators can backfill if needed.
-- (We keep them nullable to avoid blocking startup if there are pre-existing rows.)
-- If your DB has no legacy rows (or you have backfilled), we tighten to NOT NULL automatically.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM nhsa_codes WHERE raw_document_id IS NULL) THEN
        ALTER TABLE nhsa_codes ALTER COLUMN raw_document_id SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM nhsa_codes WHERE source_run_id IS NULL) THEN
        ALTER TABLE nhsa_codes ALTER COLUMN source_run_id SET NOT NULL;
    END IF;
END $$;

-- Keep history by month; rollback is possible per run_id/month without overwriting previous snapshots.
DO $$
BEGIN
    -- Legacy constraint enforced unique(code); drop it to allow multiple months.
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'nhsa_codes_code_key'
    ) THEN
        ALTER TABLE nhsa_codes DROP CONSTRAINT nhsa_codes_code_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_nhsa_codes_code_month ON nhsa_codes (code, snapshot_month);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_code ON nhsa_codes (code);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'idx_nhsa_codes_month')
       AND NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'idx_nhsa_codes_snapshot_month') THEN
        ALTER INDEX idx_nhsa_codes_month RENAME TO idx_nhsa_codes_snapshot_month;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_nhsa_codes_snapshot_month ON nhsa_codes (snapshot_month);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_source_run_id ON nhsa_codes (source_run_id);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_raw_document_id ON nhsa_codes (raw_document_id);
