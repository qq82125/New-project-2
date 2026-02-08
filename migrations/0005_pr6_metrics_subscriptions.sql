-- PR6: daily metrics and subscription digest enhancements

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS subscriber_key VARCHAR(120) NOT NULL DEFAULT 'default';
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS webhook_url TEXT;
CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber_key ON subscriptions(subscriber_key);

CREATE TABLE IF NOT EXISTS daily_digest_runs (
    id BIGSERIAL PRIMARY KEY,
    digest_date DATE NOT NULL,
    subscriber_key VARCHAR(120) NOT NULL,
    channel VARCHAR(20) NOT NULL DEFAULT 'webhook',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_digest_runs_unique
ON daily_digest_runs(digest_date, subscriber_key, channel);

CREATE INDEX IF NOT EXISTS idx_daily_digest_runs_status ON daily_digest_runs(status);
CREATE INDEX IF NOT EXISTS idx_daily_digest_runs_date ON daily_digest_runs(digest_date DESC);
