-- LRI V1: lri_scores table + config seed (admin_configs.lri_v1_config)
--
-- Append-only by default. CLI supports optional "upsert by (registration_id, date, model_version)" mode
-- by deleting existing rows in that window before inserting.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS lri_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id UUID NOT NULL REFERENCES registrations(id),
    product_id UUID NULL REFERENCES products(id),
    methodology_id UUID NULL REFERENCES methodology_master(id),

    -- inputs
    tte_days INTEGER NULL,
    renewal_count INTEGER NOT NULL DEFAULT 0,
    competitive_count INTEGER NOT NULL DEFAULT 0,
    gp_new_12m INTEGER NOT NULL DEFAULT 0,

    -- component scores (raw)
    tte_score INTEGER NOT NULL DEFAULT 0,
    rh_score INTEGER NOT NULL DEFAULT 0,
    cd_score INTEGER NOT NULL DEFAULT 0,
    gp_score INTEGER NOT NULL DEFAULT 0,

    lri_total INTEGER NOT NULL DEFAULT 0,
    lri_norm NUMERIC(8, 4) NOT NULL DEFAULT 0,
    risk_level VARCHAR(20) NOT NULL,
    model_version VARCHAR(40) NOT NULL DEFAULT 'lri_v1',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_run_id BIGINT NULL REFERENCES source_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_lri_scores_registration_id
    ON lri_scores (registration_id);
CREATE INDEX IF NOT EXISTS idx_lri_scores_calculated_at
    ON lri_scores (calculated_at);
CREATE INDEX IF NOT EXISTS idx_lri_scores_risk_level
    ON lri_scores (risk_level);
CREATE INDEX IF NOT EXISTS idx_lri_scores_model_version
    ON lri_scores (model_version);

-- Seed config (idempotent). Stored as structured JSON.
INSERT INTO admin_configs (config_key, config_value)
VALUES (
  'lri_v1_config',
  '{
    "enabled": true,
    "nightly_enabled": true,
    "max_raw_total": 130,
    "tte_bins": [
      {"lte": 0, "score": 60, "label": "expired"},
      {"lte": 30, "score": 45, "label": "0-30d"},
      {"lte": 90, "score": 30, "label": "31-90d"},
      {"lte": 180, "score": 18, "label": "91-180d"},
      {"lte": 365, "score": 8, "label": "181-365d"},
      {"lte": 99999, "score": 0, "label": ">365d"}
    ],
    "rh_bins": [
      {"lte": 0, "score": 25, "label": "no_renew"},
      {"lte": 1, "score": 15, "label": "renew_1"},
      {"lte": 2, "score": 8, "label": "renew_2"},
      {"lte": 99999, "score": 0, "label": "renew_3plus"}
    ],
    "cd_bins": [
      {"lte": 3, "score": 0, "label": "low_comp"},
      {"lte": 10, "score": 10, "label": "mid_comp"},
      {"lte": 30, "score": 20, "label": "high_comp"},
      {"lte": 100, "score": 30, "label": "very_high"},
      {"lte": 999999, "score": 40, "label": "extreme"}
    ],
    "gp_bins": [
      {"lte": 0, "score": 0, "label": "no_growth"},
      {"lte": 5, "score": 6, "label": "low"},
      {"lte": 20, "score": 14, "label": "mid"},
      {"lte": 80, "score": 22, "label": "high"},
      {"lte": 999999, "score": 28, "label": "extreme"}
    ],
    "risk_levels": [
      {"level": "CRITICAL", "gte": 80},
      {"level": "HIGH", "gte": 60},
      {"level": "MID", "gte": 40},
      {"level": "LOW", "gte": 0}
    ]
  }'::jsonb
)
ON CONFLICT (config_key) DO NOTHING;

