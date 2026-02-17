-- Rollback for migrations/0026_add_procurement_minimal.sql

DROP TABLE IF EXISTS procurement_registration_map;
DROP TABLE IF EXISTS procurement_results;
DROP TABLE IF EXISTS procurement_lots;
DROP TABLE IF EXISTS procurement_projects;

