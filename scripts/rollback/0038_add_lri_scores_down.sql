-- Rollback for 0038_add_lri_scores.sql

DROP TABLE IF EXISTS lri_scores;
DELETE FROM admin_configs WHERE config_key = 'lri_v1_config';

