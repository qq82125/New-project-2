-- Rollback for 0064_add_udi_quarantine_events.sql

DROP INDEX IF EXISTS idx_udi_quarantine_events_di;
DROP INDEX IF EXISTS idx_udi_quarantine_events_reg_no;
DROP INDEX IF EXISTS idx_udi_quarantine_events_event_type;
DROP INDEX IF EXISTS idx_udi_quarantine_events_source_run_id;
DROP TABLE IF EXISTS udi_quarantine_events;
