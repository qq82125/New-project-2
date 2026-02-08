-- PR-E: data sources management

CREATE TABLE IF NOT EXISTS data_sources (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL,
    config_encrypted TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_sources_active ON data_sources(is_active);

-- Only one active data source is allowed.
CREATE UNIQUE INDEX IF NOT EXISTS uq_data_sources_single_active ON data_sources(is_active) WHERE is_active;

