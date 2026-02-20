-- Rollback for 0060_add_allowlist_audit_and_param_key_version.sql

DROP INDEX IF EXISTS idx_product_params_param_key_version;
ALTER TABLE product_params
    DROP COLUMN IF EXISTS param_key_version;

DELETE FROM admin_configs WHERE config_key IN (
  'udi_params_allowlist_version',
  'udi_params_allowlist_changed_by',
  'udi_params_allowlist_changed_at',
  'udi_params_allowlist_change_reason'
);
