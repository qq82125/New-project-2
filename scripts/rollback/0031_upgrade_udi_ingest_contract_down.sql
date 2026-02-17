-- Rollback for 0031_upgrade_udi_ingest_contract.sql
-- Keep idempotent and non-destructive to legacy columns.

DROP INDEX IF EXISTS idx_pending_udi_links_resolved_at;
DROP INDEX IF EXISTS idx_pending_udi_links_reason_code;
DROP INDEX IF EXISTS idx_product_udi_map_match_type;

ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS resolved_by;
ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS resolved_at;
ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS candidate_product_name;
ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS candidate_company_name;
ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS raw_id;
ALTER TABLE pending_udi_links DROP COLUMN IF EXISTS reason_code;

ALTER TABLE product_udi_map DROP COLUMN IF EXISTS match_type;

