-- Rollback for migrations/0028_add_source_contract_tables.sql

DROP TABLE IF EXISTS pending_udi_links;
DROP TABLE IF EXISTS udi_di_master;
DROP TABLE IF EXISTS product_udi_map;
DROP TABLE IF EXISTS raw_source_records;

