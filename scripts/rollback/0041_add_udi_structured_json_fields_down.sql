-- Rollback for 0041_add_udi_structured_json_fields.sql
-- Drop the newly added columns and index (safe even if partially applied).

DROP INDEX IF EXISTS idx_udi_di_master_registration_no_norm;

ALTER TABLE udi_di_master
    DROP COLUMN IF EXISTS storage_json;

ALTER TABLE udi_di_master
    DROP COLUMN IF EXISTS packaging_json;

ALTER TABLE udi_di_master
    DROP COLUMN IF EXISTS registration_no_norm;

ALTER TABLE udi_di_master
    DROP COLUMN IF EXISTS has_cert;

