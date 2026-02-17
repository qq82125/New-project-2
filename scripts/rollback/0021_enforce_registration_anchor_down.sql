-- Rollback for migrations/0021_enforce_registration_anchor.sql
--
-- Notes:
-- - Only drops objects created by this migration (by name).
-- - If your environment already had equivalent indexes with the same names,
--   dropping them would affect performance. Names were chosen to be migration-specific.

DROP INDEX IF EXISTS idx_products_reg_no_anchor;
DROP INDEX IF EXISTS idx_products_registration_id_anchor;
DROP INDEX IF EXISTS idx_products_reg_no_ivd_anchor;

DROP INDEX IF EXISTS idx_product_variants_registry_no_anchor;
DROP INDEX IF EXISTS idx_product_variants_product_id_anchor;

DROP INDEX IF EXISTS uq_registrations_registration_no_anchor;

