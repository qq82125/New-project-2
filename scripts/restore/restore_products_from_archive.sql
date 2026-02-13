-- Restore archived products back to products table.
-- Optional: add "AND pa.cleanup_run_id = <run_id>" to scope a specific cleanup run.

INSERT INTO products (
    id, udi_di, reg_no, name, class, approved_date, expiry_date,
    model, specification, category, status,
    is_ivd, ivd_category, ivd_subtypes, ivd_reason, ivd_version,
    company_id, registration_id, raw_json, raw, created_at, updated_at
)
SELECT
    pa.id, pa.udi_di, pa.reg_no, pa.name, pa.class, pa.approved_date, pa.expiry_date,
    pa.model, pa.specification, pa.category, pa.status,
    pa.is_ivd, pa.ivd_category, pa.ivd_subtypes, pa.ivd_reason, pa.ivd_version,
    pa.company_id, pa.registration_id, pa.raw_json, pa.raw, pa.created_at, pa.updated_at
FROM products_archive pa
WHERE NOT EXISTS (
    SELECT 1
    FROM products p
    WHERE p.id = pa.id OR p.udi_di = pa.udi_di
);
