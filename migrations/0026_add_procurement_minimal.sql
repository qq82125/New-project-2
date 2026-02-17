-- Add minimal procurement structure (projects/lots/results/registration map).
--
-- Pattern: follow NHSA ingest style
-- - Evidence: raw_documents
-- - Run: source_runs
-- - Structured: procurement_* tables

CREATE TABLE IF NOT EXISTS procurement_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    province TEXT NOT NULL,
    title TEXT NOT NULL,
    publish_date DATE NULL,
    status TEXT NULL,
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    source_run_id BIGINT NOT NULL REFERENCES source_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_projects_province
    ON procurement_projects (province);
CREATE INDEX IF NOT EXISTS idx_procurement_projects_publish_date
    ON procurement_projects (publish_date);
CREATE INDEX IF NOT EXISTS idx_procurement_projects_source_run_id
    ON procurement_projects (source_run_id);

CREATE TABLE IF NOT EXISTS procurement_lots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES procurement_projects(id),
    lot_name TEXT NULL,
    catalog_item_raw TEXT NULL,
    catalog_item_std TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_lots_project_id
    ON procurement_lots (project_id);

CREATE TABLE IF NOT EXISTS procurement_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id UUID NOT NULL REFERENCES procurement_lots(id),
    win_company_id UUID NULL REFERENCES companies(id),
    win_company_text TEXT NULL,
    bid_price NUMERIC(18,6) NULL,
    currency TEXT NULL,
    publish_date DATE NULL,
    raw_document_id UUID NOT NULL REFERENCES raw_documents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_results_lot_id
    ON procurement_results (lot_id);
CREATE INDEX IF NOT EXISTS idx_procurement_results_publish_date
    ON procurement_results (publish_date);
CREATE INDEX IF NOT EXISTS idx_procurement_results_win_company_id
    ON procurement_results (win_company_id);

CREATE TABLE IF NOT EXISTS procurement_registration_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id UUID NOT NULL REFERENCES procurement_lots(id),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    match_type TEXT NOT NULL DEFAULT 'rule',
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_registration_map_lot_id
    ON procurement_registration_map (lot_id);
CREATE INDEX IF NOT EXISTS idx_procurement_registration_map_registration_id
    ON procurement_registration_map (registration_id);

-- Prevent duplicates per lot-registration.
CREATE UNIQUE INDEX IF NOT EXISTS uq_procurement_registration_map_lot_reg
    ON procurement_registration_map (lot_id, registration_id);

