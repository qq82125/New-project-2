DROP INDEX IF EXISTS idx_pending_udi_links_confidence;

ALTER TABLE pending_udi_links
    DROP COLUMN IF EXISTS linked_by,
    DROP COLUMN IF EXISTS reversible,
    DROP COLUMN IF EXISTS confidence,
    DROP COLUMN IF EXISTS match_reason;

ALTER TABLE product_udi_map
    DROP COLUMN IF EXISTS linked_by,
    DROP COLUMN IF EXISTS reversible,
    DROP COLUMN IF EXISTS match_reason,
    ALTER COLUMN confidence TYPE NUMERIC(3,2) USING confidence::numeric,
    ALTER COLUMN confidence SET DEFAULT 0.80;
