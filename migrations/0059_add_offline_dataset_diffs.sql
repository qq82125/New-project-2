-- Persist offline dataset diff summaries for admin and audit
-- Rollback: scripts/rollback/0059_add_offline_dataset_diffs_down.sql

CREATE TABLE IF NOT EXISTS offline_dataset_diffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key TEXT NOT NULL,
    from_dataset_id UUID NOT NULL REFERENCES offline_datasets(id) ON DELETE CASCADE,
    to_dataset_id UUID NOT NULL REFERENCES offline_datasets(id) ON DELETE CASCADE,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offline_dataset_diffs_source_created
    ON offline_dataset_diffs (source_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_offline_dataset_diffs_pair
    ON offline_dataset_diffs (from_dataset_id, to_dataset_id);
