-- Rollback for migrations/0017_pr3_nhsa_codes.sql
--
-- Note: This drops the nhsa_codes snapshot table. If you need to preserve data,
-- export it before running this rollback.

DROP TABLE IF EXISTS nhsa_codes;

