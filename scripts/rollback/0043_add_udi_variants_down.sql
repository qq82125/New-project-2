-- Rollback for 0043_add_udi_variants.sql
-- Note: dropping columns is destructive; use only in controlled environments.

DROP INDEX IF EXISTS idx_product_variants_evidence_raw_document_id;
DROP INDEX IF EXISTS idx_product_variants_registration_id;
DROP INDEX IF EXISTS idx_udi_device_index_status;

ALTER TABLE product_variants DROP COLUMN IF EXISTS evidence_raw_document_id;
ALTER TABLE product_variants DROP COLUMN IF EXISTS packaging_json;
ALTER TABLE product_variants DROP COLUMN IF EXISTS registration_id;

ALTER TABLE udi_device_index DROP COLUMN IF EXISTS status;

