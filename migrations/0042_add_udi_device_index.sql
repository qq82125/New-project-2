-- 0042: UDI device index table (read-optimized, no anchor writes).
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS udi_device_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    di_norm VARCHAR(128) NOT NULL,
    registration_no_norm VARCHAR(120) NULL,
    has_cert BOOLEAN NULL,

    model_spec TEXT NULL,         -- ggxh
    sku_code TEXT NULL,           -- cphhhbh
    product_name TEXT NULL,       -- cpmctymc
    brand TEXT NULL,              -- spmc
    description TEXT NULL,        -- cpms

    category_big TEXT NULL,       -- qxlb
    class_code TEXT NULL,         -- flbm
    product_type TEXT NULL,       -- cplb

    issuer_standard TEXT NULL,    -- cpbsbmtxmc
    publish_date DATE NULL,       -- cpbsfbrq
    barcode_carrier TEXT NULL,    -- bszt

    manufacturer_cn TEXT NULL,    -- ylqxzcrbarmc
    manufacturer_en TEXT NULL,    -- ylqxzcrbarywmc
    uscc TEXT NULL,               -- tyshxydm

    packing_json JSONB NULL,      -- packings[] array (see docs/UDI_FULL_CONTRACT.md)
    storage_json JSONB NULL,      -- storages[] array (see docs/UDI_FULL_CONTRACT.md)

    mjfs TEXT NULL,
    tscchcztj TEXT NULL,
    tsccsm TEXT NULL,

    version_number INTEGER NULL,          -- versionNumber
    version_time DATE NULL,               -- versionTime
    version_status TEXT NULL,             -- versionStauts
    correction_number INTEGER NULL,       -- correctionNumber
    correction_remark TEXT NULL,          -- correctionRemark
    correction_time TEXT NULL,            -- correctionTime (string in upstream)
    device_record_key TEXT NULL,          -- deviceRecordKey

    raw_document_id UUID NULL REFERENCES raw_documents(id),
    source_run_id BIGINT NULL REFERENCES source_runs(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Backward compatible adds (for environments where table existed with fewer columns).
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS di_norm VARCHAR(128);
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS registration_no_norm VARCHAR(120);
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS has_cert BOOLEAN;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS model_spec TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS sku_code TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS product_name TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS brand TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS category_big TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS class_code TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS issuer_standard TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS publish_date DATE;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS barcode_carrier TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS manufacturer_cn TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS manufacturer_en TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS uscc TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS packing_json JSONB;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS storage_json JSONB;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS mjfs TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS tscchcztj TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS tsccsm TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS version_number INTEGER;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS version_time DATE;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS version_status TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS correction_number INTEGER;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS correction_remark TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS correction_time TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS device_record_key TEXT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS raw_document_id UUID;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS source_run_id BIGINT;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
ALTER TABLE udi_device_index ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- Ensure DI uniqueness (no duplicate rows per DI).
CREATE UNIQUE INDEX IF NOT EXISTS uq_udi_device_index_di_norm
    ON udi_device_index (di_norm);

CREATE INDEX IF NOT EXISTS idx_udi_device_index_registration_no_norm
    ON udi_device_index (registration_no_norm);

CREATE INDEX IF NOT EXISTS idx_udi_device_index_source_run_id
    ON udi_device_index (source_run_id);

CREATE INDEX IF NOT EXISTS idx_udi_device_index_publish_date
    ON udi_device_index (publish_date);

