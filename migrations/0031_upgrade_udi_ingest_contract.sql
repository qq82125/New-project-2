-- 0031: Upgrade UDI ingest contract for at-scale linking and manual resolution.
-- Safe migration: add columns only, keep backward compatibility.

-- product_udi_map: explicit match type for direct/manual binding.
ALTER TABLE product_udi_map
    ADD COLUMN IF NOT EXISTS match_type VARCHAR(20) NOT NULL DEFAULT 'direct';

CREATE INDEX IF NOT EXISTS idx_product_udi_map_match_type
    ON product_udi_map (match_type);

-- pending_udi_links: richer diagnostics and manual workflow fields.
ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50) NULL;

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS raw_id UUID NULL REFERENCES raw_source_records(id);

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS candidate_company_name TEXT NULL;

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS candidate_product_name TEXT NULL;

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ NULL;

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS resolved_by TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_pending_udi_links_reason_code
    ON pending_udi_links (reason_code);

CREATE INDEX IF NOT EXISTS idx_pending_udi_links_resolved_at
    ON pending_udi_links (resolved_at DESC);

