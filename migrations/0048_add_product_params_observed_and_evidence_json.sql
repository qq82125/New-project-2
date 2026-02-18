-- 0048: product_params evidence/observed_at enrichment for UDI allowlist
-- Idempotent

ALTER TABLE product_params
    ADD COLUMN IF NOT EXISTS evidence_json JSONB NULL,
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_product_params_observed_at
    ON product_params (observed_at DESC);
