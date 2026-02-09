-- PR-M1: Membership data model (manual grant annual membership)
--
-- Notes:
-- - users keeps the current snapshot (plan/plan_status/plan_expires_at)
-- - membership_grants keeps historical grant records (traceable)
-- - membership_events is an optional audit log (recommended)

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS plan_status TEXT NOT NULL DEFAULT 'inactive';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS membership_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    granted_by_user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
    plan TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    reason TEXT NULL,
    note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_membership_grants_user_id ON membership_grants(user_id);
CREATE INDEX IF NOT EXISTS idx_membership_grants_end_at ON membership_grants(end_at);

CREATE TABLE IF NOT EXISTS membership_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_membership_events_user_id ON membership_events(user_id);
CREATE INDEX IF NOT EXISTS idx_membership_events_event_type ON membership_events(event_type);

