-- 0043: UDI variants promotion support (registration-anchored variants).
-- Idempotent: safe to run multiple times.
--
-- Adds:
-- - product_variants.registration_id (FK -> registrations.id)
-- - product_variants.packaging_json (JSONB, packings[] array)
-- - product_variants.evidence_raw_document_id (FK -> raw_documents.id)
-- - udi_device_index.status (for binding status such as 'unbound')

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS registration_id UUID NULL REFERENCES registrations(id);

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS packaging_json JSONB NULL;

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS evidence_raw_document_id UUID NULL REFERENCES raw_documents(id);

CREATE INDEX IF NOT EXISTS idx_product_variants_registration_id
    ON product_variants (registration_id);

CREATE INDEX IF NOT EXISTS idx_product_variants_evidence_raw_document_id
    ON product_variants (evidence_raw_document_id);

ALTER TABLE udi_device_index
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NULL;

CREATE INDEX IF NOT EXISTS idx_udi_device_index_status
    ON udi_device_index (status);

