-- Enforce registration anchor (indexes/uniqueness only; no data backfill).
--
-- Goals:
-- 1) Add/strengthen lookup indexes around registration_no anchoring paths:
--    - products.reg_no
--    - products.registration_id
--    - (optional) partial index for IVD-only reg_no lookups
--    - product_variants.registry_no
--    - product_variants.product_id
-- 2) Ensure registrations.registration_no is UNIQUE (if missing, add).
--
-- Constraints:
-- - Must be idempotent.
-- - Must not change existing column types/semantics.

-- products lookup indexes
CREATE INDEX IF NOT EXISTS idx_products_reg_no_anchor
    ON products (reg_no);

CREATE INDEX IF NOT EXISTS idx_products_registration_id_anchor
    ON products (registration_id);

-- Optional: accelerate IVD-only queries by reg_no (typical UI/ops filters).
CREATE INDEX IF NOT EXISTS idx_products_reg_no_ivd_anchor
    ON products (reg_no)
    WHERE is_ivd IS TRUE AND reg_no IS NOT NULL AND btrim(reg_no) <> '';

-- product_variants lookup indexes
CREATE INDEX IF NOT EXISTS idx_product_variants_registry_no_anchor
    ON product_variants (registry_no);

CREATE INDEX IF NOT EXISTS idx_product_variants_product_id_anchor
    ON product_variants (product_id);

-- registrations.registration_no must be UNIQUE.
-- If a UNIQUE constraint or UNIQUE index already exists, do nothing.
DO $$
DECLARE
    has_unique_constraint BOOLEAN;
    has_unique_index BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
        WHERE t.relname = 'registrations'
          AND c.contype = 'u'
        GROUP BY c.oid
        HAVING array_agg(a.attname::text ORDER BY a.attname::text) = ARRAY['registration_no']::text[]
    ) INTO has_unique_constraint;

    SELECT EXISTS (
        SELECT 1
        FROM pg_class t
        JOIN pg_index ix ON ix.indrelid = t.oid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, n) ON TRUE
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
        WHERE t.relname = 'registrations'
          AND ix.indisunique IS TRUE
        GROUP BY ix.indexrelid
        HAVING array_agg(a.attname::text ORDER BY x.n) = ARRAY['registration_no']::text[]
    ) INTO has_unique_index;

    IF NOT has_unique_constraint AND NOT has_unique_index THEN
        CREATE UNIQUE INDEX IF NOT EXISTS uq_registrations_registration_no_anchor
            ON registrations (registration_no);
    END IF;
END $$;
