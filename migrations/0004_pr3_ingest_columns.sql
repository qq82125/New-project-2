-- PR3: ingest/upsert/change-detection support columns

ALTER TABLE companies ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE products ADD COLUMN IF NOT EXISTS reg_no VARCHAR(120);
ALTER TABLE products ADD COLUMN IF NOT EXISTS class VARCHAR(120);
ALTER TABLE products ADD COLUMN IF NOT EXISTS approved_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS added_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS updated_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE source_runs ADD COLUMN IF NOT EXISTS removed_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE change_log ADD COLUMN IF NOT EXISTS before_raw JSONB;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS after_raw JSONB;
ALTER TABLE change_log ADD COLUMN IF NOT EXISTS change_date TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_products_reg_no ON products(reg_no);
CREATE INDEX IF NOT EXISTS idx_products_class ON products(class);
CREATE INDEX IF NOT EXISTS idx_products_expiry_date ON products(expiry_date);
CREATE INDEX IF NOT EXISTS idx_products_approved_date ON products(approved_date);
CREATE INDEX IF NOT EXISTS idx_change_log_change_date ON change_log(change_date DESC);
