-- Rollback for migrations/0030_add_source_registry.sql

DROP TABLE IF EXISTS source_configs;
DROP TABLE IF EXISTS source_definitions;

