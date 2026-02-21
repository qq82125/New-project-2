-- Health check 1: core table cardinality
SELECT
  'core_counts' AS check_name,
  (SELECT COUNT(*) FROM registrations) AS registrations_rows,
  (SELECT COUNT(*) FROM products) AS products_rows,
  (SELECT COUNT(*) FROM source_runs) AS source_runs_rows,
  (SELECT COUNT(*) FROM daily_metrics) AS daily_metrics_rows;

-- Health check 2: registration_no quality (null/blank + duplicate)
WITH reg_norm AS (
  SELECT
    id,
    registration_no,
    btrim(COALESCE(registration_no, '')) AS registration_no_trim
  FROM registrations
),
dup AS (
  SELECT registration_no_trim, COUNT(*) AS cnt
  FROM reg_norm
  WHERE registration_no_trim <> ''
  GROUP BY registration_no_trim
  HAVING COUNT(*) > 1
)
SELECT
  'registration_no_quality' AS check_name,
  (SELECT COUNT(*) FROM reg_norm WHERE registration_no IS NULL OR registration_no_trim = '') AS null_or_blank_count,
  (SELECT COALESCE(SUM(cnt), 0) FROM dup) AS duplicate_row_count;

-- Health check 3: products anchor ratio (has registration_id)
SELECT
  'product_anchor_ratio' AS check_name,
  COUNT(*) AS products_total,
  COUNT(*) FILTER (WHERE registration_id IS NOT NULL) AS anchored_products,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE registration_id IS NOT NULL)
    / NULLIF(COUNT(*), 0),
    2
  ) AS anchored_pct
FROM products;

-- Health check 4: latest ingest/run freshness
SELECT
  'run_freshness' AS check_name,
  MAX(started_at) AS latest_run_started_at,
  MAX(finished_at) AS latest_run_completed_at,
  MAX(created_at) AS latest_run_created_at
FROM source_runs;

-- Health check 5: status distribution in registrations
SELECT
  'registration_status_distribution' AS check_name,
  COALESCE(NULLIF(btrim(status), ''), 'unknown') AS status,
  COUNT(*) AS row_count
FROM registrations
GROUP BY 1, 2
ORDER BY row_count DESC, status ASC;
