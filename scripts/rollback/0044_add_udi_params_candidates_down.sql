-- Rollback for 0044_add_udi_params_candidates.sql
-- Note: dropping columns is destructive; use only in controlled environments.

DROP INDEX IF EXISTS idx_param_dictionary_candidates_observed_at;
DROP INDEX IF EXISTS idx_param_dictionary_candidates_source;
DROP INDEX IF EXISTS uq_param_dictionary_candidates_source_tag_run;
DROP TABLE IF EXISTS param_dictionary_candidates;

ALTER TABLE udi_device_index DROP COLUMN IF EXISTS scbssfbhph;
ALTER TABLE udi_device_index DROP COLUMN IF EXISTS scbssfbhsxrq;
ALTER TABLE udi_device_index DROP COLUMN IF EXISTS scbssfbhscrq;
ALTER TABLE udi_device_index DROP COLUMN IF EXISTS scbssfbhxlh;

-- We do NOT delete admin_configs['udi_params_allowlist'] on rollback because it may be edited by admins.

