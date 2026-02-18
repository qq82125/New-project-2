-- 0044: UDI params candidate pool + allowlist seed + label fields on udi_device_index.
-- Idempotent: safe to run multiple times.

-- A) Candidate pool snapshots (per column/tag)
CREATE TABLE IF NOT EXISTS param_dictionary_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(40) NOT NULL,
    xml_tag TEXT NOT NULL,
    count_total BIGINT NOT NULL DEFAULT 0,
    count_non_empty BIGINT NOT NULL DEFAULT 0,
    empty_rate NUMERIC(6,4) NOT NULL DEFAULT 0,
    sample_values JSONB NULL,
    source_run_id BIGINT NULL REFERENCES source_runs(id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_param_dictionary_candidates_source_tag_run
    ON param_dictionary_candidates (source, xml_tag, source_run_id);

CREATE INDEX IF NOT EXISTS idx_param_dictionary_candidates_source
    ON param_dictionary_candidates (source);

CREATE INDEX IF NOT EXISTS idx_param_dictionary_candidates_observed_at
    ON param_dictionary_candidates (observed_at DESC);

-- B) UDI label fields: store in udi_device_index so we can compute params without re-reading XML.
ALTER TABLE udi_device_index
    ADD COLUMN IF NOT EXISTS scbssfbhxlh TEXT NULL,   -- LABEL_SERIAL_NO
    ADD COLUMN IF NOT EXISTS scbssfbhscrq TEXT NULL,  -- LABEL_PROD_DATE
    ADD COLUMN IF NOT EXISTS scbssfbhsxrq TEXT NULL,  -- LABEL_EXP_DATE
    ADD COLUMN IF NOT EXISTS scbssfbhph TEXT NULL;    -- LABEL_LOT

-- C) Default allowlist seed (admin_configs)
INSERT INTO admin_configs (config_key, config_value)
VALUES (
    'udi_params_allowlist',
    '{
      "version": 1,
      "source": "UDI",
      "allowlist": [
        "STORAGE",
        "STERILIZATION_METHOD",
        "SPECIAL_STORAGE_COND",
        "SPECIAL_STORAGE_NOTE",
        "LABEL_SERIAL_NO",
        "LABEL_PROD_DATE",
        "LABEL_EXP_DATE",
        "LABEL_LOT"
      ]
    }'::jsonb
)
ON CONFLICT (config_key) DO NOTHING;

