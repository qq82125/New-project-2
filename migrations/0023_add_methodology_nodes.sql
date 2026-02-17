-- Add methodology_nodes (methodology tree V1).
--
-- No data backfill in this migration.

CREATE TABLE IF NOT EXISTS methodology_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    parent_id UUID NULL REFERENCES methodology_nodes(id),
    level INTEGER NOT NULL DEFAULT 1,
    synonyms JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_methodology_nodes_name
    ON methodology_nodes (name);

CREATE INDEX IF NOT EXISTS idx_methodology_nodes_parent_id
    ON methodology_nodes (parent_id);

CREATE INDEX IF NOT EXISTS idx_methodology_nodes_level
    ON methodology_nodes (level);

