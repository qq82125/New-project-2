ALTER TABLE registrations
    ADD COLUMN IF NOT EXISTS field_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
