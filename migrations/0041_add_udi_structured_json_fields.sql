-- 0041: Add structured JSON fields for UDI contract (packaging/storage) on udi_di_master.
-- This is additive and idempotent.

ALTER TABLE udi_di_master
    ADD COLUMN IF NOT EXISTS has_cert BOOLEAN NULL;

ALTER TABLE udi_di_master
    ADD COLUMN IF NOT EXISTS registration_no_norm VARCHAR(120) NULL;

ALTER TABLE udi_di_master
    ADD COLUMN IF NOT EXISTS packaging_json JSONB NULL;

ALTER TABLE udi_di_master
    ADD COLUMN IF NOT EXISTS storage_json JSONB NULL;

CREATE INDEX IF NOT EXISTS idx_udi_di_master_registration_no_norm
    ON udi_di_master (registration_no_norm);

