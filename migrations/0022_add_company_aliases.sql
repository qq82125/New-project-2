-- Add company alias system (minimal viable).
--
-- Table: company_aliases
-- - alias_name: normalized key used for matching
-- - company_id: canonical companies.id
-- - confidence/source: provenance of alias mapping
--
-- No data backfill in this migration.

CREATE TABLE IF NOT EXISTS company_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias_name TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    source TEXT NOT NULL DEFAULT 'rule',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One alias key should map to a single company.
CREATE UNIQUE INDEX IF NOT EXISTS uq_company_aliases_alias_name
    ON company_aliases (alias_name);

CREATE INDEX IF NOT EXISTS idx_company_aliases_alias_name
    ON company_aliases (alias_name);

CREATE INDEX IF NOT EXISTS idx_company_aliases_company_id
    ON company_aliases (company_id);

