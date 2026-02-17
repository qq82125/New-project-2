-- DEPRECATED NO-OP MIGRATION
-- ---------------------------------------------------------------------------
-- pending_records canonical schema/workflow is managed by:
--   migrations/0031_add_pending_records.sql
--
-- This file name (0033_add_pending_records.sql) is retained ONLY for historical
-- migration ordering/reference compatibility.
--
-- Contract:
-- - Do NOT create/alter pending_records here.
-- - Do NOT introduce a different status default.
-- - Do NOT introduce/rebuild a different status constraint.
--
-- Any future pending_records schema changes must be done in a new migration
-- after 0033, with explicit compatibility + rollback.
-- ---------------------------------------------------------------------------

SELECT 1;
