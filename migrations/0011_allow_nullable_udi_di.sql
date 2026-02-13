-- Allow products.udi_di to be nullable (store real UDI-DI only).
-- Also cleanup historical fallback values like 'reg:<reg_no>' to NULL.

ALTER TABLE products
    ALTER COLUMN udi_di DROP NOT NULL;

-- Normalize historical fallback: keep reg_no as identifier, do not store it in udi_di.
UPDATE products
SET udi_di = NULL
WHERE udi_di ILIKE 'reg:%';

