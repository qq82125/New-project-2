-- Signal Engine V1: unified offline-computed signal store
-- Supports entity_type in ('registration','track','company'), window currently '12m'.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS signal_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL,
    entity_id VARCHAR(120) NOT NULL,
    "window" VARCHAR(20) NOT NULL DEFAULT '12m',
    as_of_date DATE NOT NULL,
    level VARCHAR(30) NOT NULL,
    score NUMERIC(10, 4) NOT NULL DEFAULT 0,
    factors JSONB NOT NULL DEFAULT '[]'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_signal_scores_entity_window_date
        UNIQUE (entity_type, entity_id, "window", as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_signal_scores_entity_window_date_level
    ON signal_scores (entity_type, "window", as_of_date, level);

CREATE INDEX IF NOT EXISTS idx_signal_scores_entity_window_date_score_desc
    ON signal_scores (entity_type, "window", as_of_date, score DESC);
