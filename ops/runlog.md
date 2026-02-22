# UDI Run Log

## Run 41 Snapshot (2026-02-22 12:46:13 CST)
- source_run_id: `41`
- outlier_threshold: `100`
- outliers in `udi_outliers`: `16`
- variants quarantine status: enabled (historical `outlier_regno_skipped=7772`)

## This Round Execution Summary

### Phase 1 - Expand `udi:params` (default skip outliers)
Command:
```bash
docker compose exec worker python -m app.workers.cli udi:params --execute --source-run-id 41 --limit 200000 --batch-size 500
```
Key output:
- scanned: `0`
- params_written: `0`
- outliers_skipped_count: `7772`
- include_outliers: `false`
- allowlisted_key_count: `0`

### Phase 2 - Regress duplicate `products.reg_no` (visible rows only)
Command:
```bash
docker compose exec db psql -U nmpa -d nmpa -c "SELECT COUNT(*) AS dup_regnos FROM (SELECT reg_no FROM products WHERE reg_no IS NOT NULL AND btrim(reg_no) <> '' AND is_hidden = FALSE GROUP BY reg_no HAVING COUNT(*) > 1) t;"
```
Key output:
- dup_regnos: `0`

### Phase 3/4 - Outlier triage artifacts
Generated:
- `reports/outlier_triage_run41.csv`
- `reports/outlier_triage_run41.md`

Notes:
- Current bottleneck is not outlier skip logic; it is allowlist empty (`allowlisted_key_count=0`).
- Next effective action is to load/activate allowlist keys, then rerun `udi:params`.
