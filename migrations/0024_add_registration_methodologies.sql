-- Add registration_methodologies (registration -> methodology mapping).
--
-- No data backfill in this migration.

CREATE TABLE IF NOT EXISTS registration_methodologies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    methodology_id UUID NOT NULL REFERENCES methodology_nodes(id),
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    source TEXT NOT NULL DEFAULT 'rule',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_registration_methodologies_registration_id
    ON registration_methodologies (registration_id);

CREATE INDEX IF NOT EXISTS idx_registration_methodologies_methodology_id
    ON registration_methodologies (methodology_id);

-- Prevent duplicates (allow multiple methodologies per registration, but one row per pair).
CREATE UNIQUE INDEX IF NOT EXISTS uq_registration_methodologies_reg_method
    ON registration_methodologies (registration_id, methodology_id);

