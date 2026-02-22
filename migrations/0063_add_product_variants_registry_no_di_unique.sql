-- 0063: strengthen product_variants idempotency for DI spec-layer writes.
-- di is already unique; add explicit (registry_no, di) unique index for composite safety checks.

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_variants_registry_no_di
    ON product_variants (registry_no, di)
    WHERE registry_no IS NOT NULL;
