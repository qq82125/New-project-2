-- Ontology V1 (minimal): methodology_master + product_methodology_map
--
-- Goal: store a small, editable methodology dictionary and map it to products for downstream analytics.
-- This is NOT a full graph/ontology; it is a minimal, audit-friendly starting point.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS methodology_master (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name_cn TEXT NOT NULL,
    name_en TEXT NULL,
    aliases TEXT[] NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_methodology_master_is_active
    ON methodology_master(is_active);

CREATE TABLE IF NOT EXISTS product_methodology_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    methodology_id UUID NOT NULL REFERENCES methodology_master(id),
    evidence_raw_document_id UUID NULL REFERENCES raw_documents(id),
    evidence_text TEXT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 0.80,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_product_methodology UNIQUE (product_id, methodology_id)
);

CREATE INDEX IF NOT EXISTS idx_product_methodology_product_id
    ON product_methodology_map(product_id);

CREATE INDEX IF NOT EXISTS idx_product_methodology_methodology_id
    ON product_methodology_map(methodology_id);

-- Seed TOP20 methodologies (idempotent).
INSERT INTO methodology_master (code, name_cn, name_en, aliases)
VALUES
  ('PCR', 'PCR', 'PCR', ARRAY['PCR','聚合酶链式反应','扩增','核酸扩增']::text[]),
  ('QPCR', 'qPCR', 'qPCR', ARRAY['qPCR','QPCR','实时荧光PCR','实时定量PCR']::text[]),
  ('DPCR', 'dPCR', 'dPCR', ARRAY['dPCR','DPCR','数字PCR']::text[]),
  ('NGS', 'NGS', 'NGS', ARRAY['NGS','二代测序','高通量测序']::text[]),
  ('MNGS', 'mNGS', 'mNGS', ARRAY['mNGS','MNGS','宏基因组测序','宏基因组']::text[]),
  ('CLIA', '化学发光', 'CLIA', ARRAY['CLIA','化学发光','化学发光免疫分析','发光']::text[]),
  ('ELISA', 'ELISA', 'ELISA', ARRAY['ELISA','酶联免疫','酶联免疫吸附']::text[]),
  ('ICT', '免疫层析', 'Immunochromatography', ARRAY['免疫层析','胶体金','金标','层析']::text[]),
  ('POCT', 'POCT', 'POCT', ARRAY['POCT','床旁检测','即时检测','快速检测']::text[]),
  ('FLOW', '流式细胞', 'Flow cytometry', ARRAY['流式','流式细胞','流式细胞术']::text[]),
  ('BIOCHEM', '生化', 'Biochemistry', ARRAY['生化','生化分析','临床生化']::text[]),
  ('IMMUNO', '免疫分析', 'Immunoassay', ARRAY['免疫','免疫分析','免疫检测']::text[]),
  ('MS', '质谱', 'Mass spectrometry', ARRAY['质谱','MS','LC-MS','LCMS']::text[]),
  ('HPLC', '液相色谱', 'HPLC', ARRAY['HPLC','高效液相','液相色谱']::text[]),
  ('GC', '气相色谱', 'GC', ARRAY['GC','气相色谱']::text[]),
  ('ECL', '电化学发光', 'ECL', ARRAY['电化学发光','ECL']::text[]),
  ('RAPID', '快速检测', 'Rapid test', ARRAY['快速','快速检测','快检']::text[]),
  ('HEMAT', '血液学', 'Hematology', ARRAY['血液','血液学','血常规']::text[]),
  ('COAG', '凝血', 'Coagulation', ARRAY['凝血','凝固']::text[]),
  ('URINE', '尿液分析', 'Urinalysis', ARRAY['尿液','尿常规']::text[])
ON CONFLICT (code) DO NOTHING;

