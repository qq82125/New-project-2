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

---
## UDI Restore Run (2026-02-22)

udi_release: UDID_FULL_RELEASE_20260205
source_run_id (UDI_DI): unknown   # 如果不确定就写 unknown，但保持字段存在
index_run_id (udi:index/promote/variants/params): 41

outliers:
  threshold: 100
  outlier_registrations: 16
  outlier_di_skipped (observed): 7772

variants (run=41):
  scanned: 10000
  bound/upserted: 2228
  outlier_regno_skipped: 7772
  multi_bind_di_skipped: 0
  failed: 0

params (Phase1 run=41):
  limit: 200000
  batch_size: 500
  scanned: 0
  params_written: 0
  distinct_products_updated: 0
  outliers_skipped_count: 7772
  include_outliers: false

notes:
- products reg_no duplicates (is_hidden=false): 0
- next: outlier triage report reports/outlier_triage_run41.*
---

---
## Type A Outlier Fix (run=41)

fixed_regnos:
  - 国械注准20243131618: 2582 -> 36
  - 国械注准20233130399: 2234 -> 81

outliers_status_update:
  before: open=16
  after: open=14, resolved=2

replay_commit: 58ac4e3
params_rebackfill: executed
audit_after_fix: completed
---
