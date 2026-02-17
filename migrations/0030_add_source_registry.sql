-- Source Registry: static source definitions + runtime editable source configs.
-- This migration is additive and does not change existing ingest logic.

CREATE TABLE IF NOT EXISTS source_definitions (
    source_key VARCHAR(80) PRIMARY KEY,
    display_name VARCHAR(160) NOT NULL,
    entity_scope VARCHAR(40) NOT NULL,
    default_evidence_grade VARCHAR(1) NOT NULL DEFAULT 'C',
    parser_key VARCHAR(120) NOT NULL,
    enabled_by_default BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_source_definitions_grade
        CHECK (default_evidence_grade IN ('A', 'B', 'C', 'D'))
);

CREATE INDEX IF NOT EXISTS idx_source_definitions_entity_scope
    ON source_definitions (entity_scope);

CREATE TABLE IF NOT EXISTS source_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(80) NOT NULL REFERENCES source_definitions(source_key) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    schedule_cron TEXT NULL,
    fetch_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    parse_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    upsert_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_run_at TIMESTAMPTZ NULL,
    last_status VARCHAR(20) NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_source_configs_source_key UNIQUE (source_key)
);

CREATE INDEX IF NOT EXISTS idx_source_configs_enabled
    ON source_configs (enabled);
CREATE INDEX IF NOT EXISTS idx_source_configs_last_run_at
    ON source_configs (last_run_at DESC);

-- Seed minimal static source catalog (idempotent).
INSERT INTO source_definitions (
    source_key, display_name, entity_scope, default_evidence_grade, parser_key, enabled_by_default
) VALUES
    ('NMPA_REG', 'NMPA注册产品库（主数据源）', 'REGISTRATION', 'A', 'nmpa_reg_parser', TRUE),
    ('UDI_DI', 'UDI_DI（注册证/DI/包装）', 'UDI', 'A', 'udi_di_parser', TRUE),
    ('PROCUREMENT_GD', '广东集采公告', 'PROCUREMENT', 'B', 'procurement_gd_parser', FALSE),
    ('NHSA', '国家医保（NHSA）', 'NHSA', 'A', 'nhsa_parser', FALSE)
ON CONFLICT (source_key) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    entity_scope = EXCLUDED.entity_scope,
    default_evidence_grade = EXCLUDED.default_evidence_grade,
    parser_key = EXCLUDED.parser_key,
    enabled_by_default = EXCLUDED.enabled_by_default,
    updated_at = NOW();

