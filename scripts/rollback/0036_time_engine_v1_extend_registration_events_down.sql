-- Rollback for 0036_time_engine_v1_extend_registration_events.sql
--
-- We keep added columns for safety (dropping columns is destructive and may break existing code paths).
-- This rollback removes the new indexes only.

DROP INDEX IF EXISTS uq_registration_events_reg_seq;
DROP INDEX IF EXISTS idx_registration_events_event_type;
DROP INDEX IF EXISTS idx_registration_events_observed_at;

