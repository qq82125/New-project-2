-- 0047: udi:params engineering hardening (checkpoint + candidate sample meta + allowlist upsert key)
-- Idempotent and backward-compatible.

-- A) Resume checkpoint for long-running UDI jobs
CREATE TABLE IF NOT EXISTS udi_jobs_checkpoint (
    job_name VARCHAR(120) PRIMARY KEY,
    cursor VARCHAR(255) NOT NULL DEFAULT '',
    meta JSONB NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_udi_jobs_checkpoint_updated_at
    ON udi_jobs_checkpoint (updated_at DESC);

-- B) Candidate sampling metadata for param_dictionary_candidates
ALTER TABLE param_dictionary_candidates
    ADD COLUMN IF NOT EXISTS sample_meta JSONB NULL;

-- C) product_params key for allowlist upsert by product anchor
ALTER TABLE product_params
    ADD COLUMN IF NOT EXISTS product_id UUID NULL REFERENCES products(id);

CREATE INDEX IF NOT EXISTS idx_product_params_product_id
    ON product_params (product_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_params_allowlist_product_code
    ON product_params (product_id, param_code, extract_version)
    WHERE product_id IS NOT NULL;
