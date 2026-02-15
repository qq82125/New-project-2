-- PR4: products_rejected idempotency (unique by source+source_key) and cleanup duplicates.

-- Backfill nulls to enable NOT NULL + unique constraint.
UPDATE products_rejected
SET source = 'unknown'
WHERE source IS NULL OR btrim(source) = '';

UPDATE products_rejected
SET source_key = 'unknown:' || id::text
WHERE source_key IS NULL OR btrim(source_key) = '';

-- Deduplicate: keep the newest rejected_at per (source, source_key).
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY source, source_key
            ORDER BY rejected_at DESC NULLS LAST, id DESC
        ) AS rn
    FROM products_rejected
)
DELETE FROM products_rejected pr
USING ranked r
WHERE pr.id = r.id AND r.rn > 1;

ALTER TABLE products_rejected
    ALTER COLUMN source SET NOT NULL,
    ALTER COLUMN source_key SET NOT NULL;

-- Enforce idempotency for rejects (same key won't create duplicates).
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_rejected_source_key
    ON products_rejected (source, source_key);

