-- Create a stable view for UDI registration-anchor enhancement source.
-- Purpose: keep data source source_query short/readable in admin UI.

CREATE OR REPLACE VIEW public.v_udi_registration_enhance AS
SELECT
  pv.di AS udi_di,
  COALESCE(NULLIF(pv.registry_no, ''), NULLIF(p.reg_no, '')) AS reg_no,
  COALESCE(NULLIF(p.name, ''), pv.product_name) AS name,
  COALESCE(NULLIF(p.model, ''), pv.model_spec) AS model,
  COALESCE(NULLIF(p.specification, ''), pv.model_spec) AS specification,
  p.category AS category,
  p.status AS status,
  p.approved_date AS approved_date,
  p.expiry_date AS expiry_date,
  p.class AS class,
  p.raw_json AS raw_json,
  p.raw AS raw,
  GREATEST(
    COALESCE(p.updated_at, TIMESTAMPTZ '1970-01-01'),
    COALESCE(pv.updated_at, TIMESTAMPTZ '1970-01-01')
  ) AS updated_at
FROM public.product_variants pv
LEFT JOIN public.products p ON p.id = pv.product_id
WHERE (p.is_ivd IS TRUE OR pv.is_ivd IS TRUE);

