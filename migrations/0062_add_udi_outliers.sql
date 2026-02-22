-- 0062: quarantine UDI outlier registration_no by DI bindings

CREATE TABLE IF NOT EXISTS udi_outliers (
    id BIGSERIAL PRIMARY KEY,
    source_run_id BIGINT NULL,
    reg_no TEXT NOT NULL,
    di_count INT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'open',
    notes TEXT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_udi_outliers_run_reg
    ON udi_outliers (source_run_id, reg_no);

CREATE INDEX IF NOT EXISTS idx_udi_outliers_source_run_id
    ON udi_outliers (source_run_id);

CREATE INDEX IF NOT EXISTS idx_udi_outliers_reg_no
    ON udi_outliers (reg_no);

CREATE INDEX IF NOT EXISTS idx_udi_outliers_status
    ON udi_outliers (status);
