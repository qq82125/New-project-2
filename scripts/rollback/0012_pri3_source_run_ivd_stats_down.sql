-- Rollback for migrations/0012_pri3_source_run_ivd_stats.sql

ALTER TABLE source_runs DROP COLUMN IF EXISTS source_notes;
ALTER TABLE source_runs DROP COLUMN IF EXISTS non_ivd_skipped_count;
ALTER TABLE source_runs DROP COLUMN IF EXISTS ivd_kept_count;
