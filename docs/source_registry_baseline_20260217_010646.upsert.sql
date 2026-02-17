-- Source Registry baseline upsert (generated from current environment)
-- File: source_registry_baseline_20260217_010646.upsert.sql
-- Note:
-- 1) This script is idempotent (upsert by source_key).
-- 2) Replace password placeholders before execute:
--    - __NMPA_DB_PASSWORD__
--    - __UDI_DB_PASSWORD__
-- 3) Run inside a transaction.

BEGIN;

-- 1) source_definitions
INSERT INTO source_definitions (
  source_key, display_name, entity_scope, default_evidence_grade, parser_key, enabled_by_default
)
VALUES
  ('NHSA', '国家医保（NHSA）', 'NHSA', 'A', 'nhsa_parser', FALSE),
  ('NMPA_REG', 'NMPA注册产品库（主数据源）', 'REGISTRATION', 'A', 'nmpa_reg_parser', TRUE),
  ('PROCUREMENT_GD', '广东集采公告', 'PROCUREMENT', 'B', 'procurement_gd_parser', FALSE),
  ('UDI_DI', 'UDI_DI（注册证/DI/包装）', 'UDI', 'A', 'udi_di_parser', TRUE)
ON CONFLICT (source_key) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  entity_scope = EXCLUDED.entity_scope,
  default_evidence_grade = EXCLUDED.default_evidence_grade,
  parser_key = EXCLUDED.parser_key,
  enabled_by_default = EXCLUDED.enabled_by_default,
  updated_at = NOW();

-- 2) source_configs
INSERT INTO source_configs (
  source_key, enabled, schedule_cron, fetch_params, parse_params, upsert_policy
)
VALUES
  (
    'NHSA',
    TRUE,
    '0 3 * * 1',
    $json${
      "file": "/app/api/data/raw/samples/nhsa_sample.csv",
      "month": "2026-02",
      "batch_size": 500,
      "lookback_days": 35
    }$json$::jsonb,
    $json${"mapping_version":"v1"}$json$::jsonb,
    $json${"anchor":"registration_no","conflict":"evidence_then_priority","priority":90,"allow_overwrite":true}$json$::jsonb
  ),
  (
    'NMPA_REG',
    TRUE,
    '0 */6 * * *',
    $json${
      "batch_size": 2000,
      "cutoff_window_hours": 6,
      "legacy_data_source": {
        "name": "NMPA注册产品库（主数据源）",
        "type": "postgres",
        "config": {
          "host": "db",
          "port": 5432,
          "database": "nmpa",
          "username": "nmpa",
          "password": "__NMPA_DB_PASSWORD__",
          "batch_size": 2000,
          "source_table": "public.products"
        }
      }
    }$json$::jsonb,
    $json${"mapping_version":"v1","strict_registration_no":true}$json$::jsonb,
    $json${"anchor":"registration_no","conflict":"evidence_then_priority","priority":100,"allow_overwrite":true}$json$::jsonb
  ),
  (
    'PROCUREMENT_GD',
    TRUE,
    '0 5 * * *',
    $json${
      "file": "/app/api/data/raw/samples/procurement_gd_sample.csv",
      "province": "GD",
      "batch_size": 1000,
      "lookback_days": 30
    }$json$::jsonb,
    $json${"mapping_version":"v1","fuzzy_match_enabled":true}$json$::jsonb,
    $json${"anchor":"registration_no","conflict":"append_only","priority":60,"allow_overwrite":false}$json$::jsonb
  ),
  (
    'UDI_DI',
    TRUE,
    '30 */6 * * *',
    $json${
      "batch_size": 2000,
      "cutoff_window_hours": 6,
      "legacy_data_source": {
        "name": "UDI注册证关联增强源（DI/GTIN/包装）",
        "type": "postgres",
        "config": {
          "host": "db",
          "port": 5432,
          "database": "nmpa",
          "username": "nmpa",
          "password": "__UDI_DB_PASSWORD__",
          "batch_size": 2000,
          "source_table": "public.product_variants"
        }
      }
    }$json$::jsonb,
    $json${"mapping_version":"v1","strict_registration_no":true}$json$::jsonb,
    $json${"anchor":"registration_no","conflict":"fill_missing_only","priority":80,"allow_overwrite":false}$json$::jsonb
  )
ON CONFLICT (source_key) DO UPDATE
SET
  enabled = EXCLUDED.enabled,
  schedule_cron = EXCLUDED.schedule_cron,
  fetch_params = EXCLUDED.fetch_params,
  parse_params = EXCLUDED.parse_params,
  upsert_policy = EXCLUDED.upsert_policy,
  updated_at = NOW();

COMMIT;

