-- PR-I3: source_runs adds IVD pipeline counters
-- Idempotent migration.

ALTER TABLE source_runs
    ADD COLUMN IF NOT EXISTS ivd_kept_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE source_runs
    ADD COLUMN IF NOT EXISTS non_ivd_skipped_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE source_runs
    ADD COLUMN IF NOT EXISTS source_notes JSONB;
