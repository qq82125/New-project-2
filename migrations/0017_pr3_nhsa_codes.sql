-- PR3.1: NHSA monthly snapshot ingestion (evidence-chain backed).

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

-- Keep history by month; rollback is possible per run_id/month without overwriting previous snapshots.
CREATE UNIQUE INDEX IF NOT EXISTS uq_nhsa_codes_code_month ON nhsa_codes (code, snapshot_month);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_code ON nhsa_codes (code);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_snapshot_month ON nhsa_codes (snapshot_month);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_source_run_id ON nhsa_codes (source_run_id);
CREATE INDEX IF NOT EXISTS idx_nhsa_codes_raw_document_id ON nhsa_codes (raw_document_id);

