ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);

CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    subscription_type VARCHAR(30) NOT NULL,
    target_value VARCHAR(255) NOT NULL,
    webhook_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_digest_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(subscription_type);
CREATE INDEX IF NOT EXISTS idx_subscriptions_target ON subscriptions(target_value);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(is_active);

CREATE TABLE IF NOT EXISTS subscription_deliveries (
    id BIGSERIAL PRIMARY KEY,
    subscription_id BIGINT NOT NULL REFERENCES subscriptions(id),
    dedup_hash VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscription_deliveries_dedup ON subscription_deliveries(subscription_id, dedup_hash);
CREATE INDEX IF NOT EXISTS idx_subscription_deliveries_status ON subscription_deliveries(status);

CREATE TABLE IF NOT EXISTS export_usage (
    id BIGSERIAL PRIMARY KEY,
    usage_date DATE NOT NULL,
    plan VARCHAR(30) NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_export_usage_daily_plan ON export_usage(usage_date, plan);

CREATE TABLE IF NOT EXISTS admin_configs (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(80) NOT NULL UNIQUE,
    config_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO admin_configs(config_key, config_value)
VALUES
('field_mapping', '{"version":"v1","source":"udi_download","notes":"default mapping"}'::jsonb),
('tag_rules', '{"rules":[{"name":"即将到期","condition":"expiry_date<90d"}]}'::jsonb)
ON CONFLICT (config_key) DO NOTHING;
