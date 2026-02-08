-- PR6 extension: email channel for subscription digest

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS channel VARCHAR(20) NOT NULL DEFAULT 'webhook';
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS email_to VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_subscriptions_channel ON subscriptions(channel);
CREATE INDEX IF NOT EXISTS idx_subscriptions_email_to ON subscriptions(email_to);
