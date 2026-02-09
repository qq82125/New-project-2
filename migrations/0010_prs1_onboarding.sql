-- PR-S1: onboarding flag

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS onboarded BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_users_onboarded ON users(onboarded);

