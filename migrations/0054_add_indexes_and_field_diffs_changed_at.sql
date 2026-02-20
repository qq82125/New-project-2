-- Performance: add indexes for structured registration fields and field_diffs time-series access.
-- Rollback: scripts/rollback/0054_add_indexes_and_field_diffs_changed_at_down.sql

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='registrations' AND column_name='origin_type'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='registrations' AND column_name='management_class'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_registrations_origin_mgmt ON registrations (origin_type, management_class)';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='registrations' AND column_name='first_year'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_registrations_first_year ON registrations (first_year)';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='registrations' AND column_name='approval_level'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_registrations_approval_level ON registrations (approval_level)';
    END IF;
END
$$;

ALTER TABLE field_diffs
    ADD COLUMN IF NOT EXISTS changed_at TIMESTAMPTZ NULL;

UPDATE field_diffs
SET changed_at = created_at
WHERE changed_at IS NULL;

ALTER TABLE field_diffs
    ALTER COLUMN changed_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_field_diffs_reg_field_changed_at
    ON field_diffs (registration_id, field_name, changed_at DESC);
