-- 0061: soft dedupe markers for products by reg_no
-- Keep duplicate rows for audit/history; hide non-canonical rows from default queries.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS superseded_by UUID NULL;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_products_superseded_by'
    ) THEN
        ALTER TABLE products
            ADD CONSTRAINT fk_products_superseded_by
            FOREIGN KEY (superseded_by) REFERENCES products(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_products_reg_no ON products (reg_no);
CREATE INDEX IF NOT EXISTS idx_products_is_hidden ON products (is_hidden);
CREATE INDEX IF NOT EXISTS idx_products_superseded_by ON products (superseded_by);
