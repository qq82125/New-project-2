# Type-A Outlier Fix Report (run=41)

## Scope
Target reg_no (only these two):
- 国械注准20243131618
- 国械注准20233130399

Constraints followed:
- No rebuild / no truncate / no full UDI rerun.
- Only local replay for the two Type-A reg_no.
- Keep 14 non-Type-A outliers unchanged in quarantine.

## Raw field shape samples (XML `zczbhhzbapzbh`)
We reverse-scanned UDI XML for DI samples under the two targets.

- reg_no = 国械注准20243131618
  - sampled raw count: 40
  - unique raw values: 1
  - sample raw: `国械注准20243131618`

- reg_no = 国械注准20233130399
  - sampled raw count: 40
  - unique raw values: 1
  - sample raw: `国械注准20233130399`

Conclusion: not a multi-regno concatenation artifact in `zczbhhzbapzbh` for these samples.

## Diagnosis
Observed before replay:
- `udi_device_index` count (run=41):
  - 国械注准20243131618: 2582
  - 国械注准20233130399: 2234
- manufacturer/product/uscc diversity: 1/1/1 for both reg_no (highly concentrated issuer/product family)
- DI prefix concentration: single prefix family per reg_no

Root cause judged as **variant over-granularity** on these two anchors (same registration_no with massive model/spec combinations), causing binding explosion in variants layer.

## Fix strategy (precise, local)
Added targeted replay CLI:
- `udi:replay-regno`

Rule used for Type-A replay (for selected reg_no only):
1. Load all DI rows from `udi_device_index` for `source_run_id=41` + target reg_no.
2. Build deterministic model family key from `model_spec/sku_code`:
   - split before `/` (plate-like models)
   - then trim tail after `×/x/X/*` (dimension tails)
   - remove trailing numeric/hole suffix
3. Keep one representative DI per family (lexicographically smallest DI).
4. Delete old variants/links for those run DI rows of the target reg_no.
5. Re-upsert selected representatives only (idempotent).

This is a split/recompute rule, not threshold masking.

## Replay commands
Dry run:
```bash
docker compose exec worker python -m app.workers.cli udi:replay-regno \
  --dry-run \
  --source-run-id 41 \
  --outlier-threshold 100 \
  --registration-no 国械注准20243131618 \
  --registration-no 国械注准20233130399
```

Execute:
```bash
docker compose exec worker python -m app.workers.cli udi:replay-regno \
  --execute \
  --source-run-id 41 \
  --outlier-threshold 100 \
  --registration-no 国械注准20243131618 \
  --registration-no 国械注准20233130399
```

## Result (after execute)
Replay output:
- scanned: 4816
- selected_for_write: 117
- deleted_variants: 4816
- deleted_links: 4815
- upserted: 117
- multi_bind_di_skipped: 0
- failed: 0

Per-reg reduction:
- 国械注准20233130399: 2234 -> 81 (family_count=81)
- 国械注准20243131618: 2582 -> 36 (family_count=36)

Validation SQL (`product_variants`):
- 国械注准20233130399: 81
- 国械注准20243131618: 36

Both dropped by at least one order of magnitude.

No new multi-bind introduced:
- `COUNT(DISTINCT registry_no) > 1` on DI for the two targets: 0 rows.

## Non-Type-A impact check
`udi_outliers` (run=41, status=open) remains:
- total: 16
- Type-A targets still open: 2
- others unchanged: 14

So the 14 non-Type-A outliers remain quarantined.

## Next step suggestion
- Keep these two reg_no under monitored replay mode.
- If future raw fields expose stronger legal sub-anchor, replace family split with explicit canonical split.
