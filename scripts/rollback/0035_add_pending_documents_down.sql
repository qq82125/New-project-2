-- Rollback for 0035_add_pending_documents.sql
-- Safe: this drops only the newly introduced table/indexes.

DROP TABLE IF EXISTS pending_documents;

