-- 0060: versioned/audited UDI allowlist + product_params.param_key_version
-- Idempotent.

ALTER TABLE product_params
    ADD COLUMN IF NOT EXISTS param_key_version INT NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_product_params_param_key_version
    ON product_params (param_key_version);

INSERT INTO admin_configs (config_key, config_value)
VALUES ('udi_params_allowlist_version', '{"value": 1}'::jsonb)
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO admin_configs (config_key, config_value)
VALUES ('udi_params_allowlist_changed_by', '{"value": "system"}'::jsonb)
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO admin_configs (config_key, config_value)
VALUES ('udi_params_allowlist_changed_at', jsonb_build_object('value', NOW()::text))
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO admin_configs (config_key, config_value)
VALUES ('udi_params_allowlist_change_reason', '{"value": "bootstrap"}'::jsonb)
ON CONFLICT (config_key) DO NOTHING;
