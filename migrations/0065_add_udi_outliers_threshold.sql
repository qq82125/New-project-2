-- 0065: add threshold metadata for udi outlier quarantine records

ALTER TABLE udi_outliers
    ADD COLUMN IF NOT EXISTS threshold INT;

UPDATE udi_outliers
SET threshold = 100
WHERE threshold IS NULL;

ALTER TABLE udi_outliers
    ALTER COLUMN threshold SET DEFAULT 100;

ALTER TABLE udi_outliers
    ALTER COLUMN threshold SET NOT NULL;
