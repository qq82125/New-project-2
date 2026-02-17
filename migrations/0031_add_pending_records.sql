-- Pending records workflow (manual registration anchor resolution)
-- Compatible with existing pending_records schema if already created.

CREATE TABLE IF NOT EXISTS pending_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(80) NOT NULL,
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    payload_hash VARCHAR(64) NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    registration_no_raw TEXT NULL,
    reason TEXT NULL,
    candidate_registry_no VARCHAR(120) NULL,
    candidate_company TEXT NULL,
    candidate_product_name TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pending_records_run_payload UNIQUE (source_run_id, payload_hash)
);

-- Backward-compatible upgrades for environments that already have pending_records.
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS candidate_registry_no VARCHAR(120) NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS candidate_company TEXT NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS candidate_product_name TEXT NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS source_run_id BIGINT NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64) NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS registration_no_raw TEXT NULL;
ALTER TABLE pending_records ADD COLUMN IF NOT EXISTS reason TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pending_records_source_run_id_fkey'
          AND conrelid = 'pending_records'::regclass
    ) THEN
        ALTER TABLE pending_records
            ADD CONSTRAINT pending_records_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES source_runs(id);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_records_run_payload
    ON pending_records (source_run_id, payload_hash);

ALTER TABLE pending_records ALTER COLUMN status SET DEFAULT 'open';

-- Normalize old statuses.
UPDATE pending_records SET status = 'open' WHERE status = 'pending';

-- Rebuild check constraint with open/resolved as primary workflow states.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_pending_records_status'
          AND conrelid = 'pending_records'::regclass
    ) THEN
        ALTER TABLE pending_records DROP CONSTRAINT chk_pending_records_status;
    END IF;
END $$;

ALTER TABLE pending_records
    ADD CONSTRAINT chk_pending_records_status
    CHECK (status IN ('open', 'resolved', 'ignored', 'pending'));

CREATE INDEX IF NOT EXISTS idx_pending_records_status
    ON pending_records (status);
CREATE INDEX IF NOT EXISTS idx_pending_records_source_key
    ON pending_records (source_key);
