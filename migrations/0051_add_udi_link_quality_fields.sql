ALTER TABLE product_udi_map
    ALTER COLUMN confidence TYPE DOUBLE PRECISION USING confidence::double precision,
    ALTER COLUMN confidence SET DEFAULT 0.80,
    ADD COLUMN IF NOT EXISTS match_reason TEXT,
    ADD COLUMN IF NOT EXISTS reversible BOOL NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS linked_by TEXT;

ALTER TABLE pending_udi_links
    ADD COLUMN IF NOT EXISTS match_reason TEXT,
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.80,
    ADD COLUMN IF NOT EXISTS reversible BOOL NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS linked_by TEXT;

CREATE INDEX IF NOT EXISTS idx_pending_udi_links_confidence
    ON pending_udi_links (confidence);
