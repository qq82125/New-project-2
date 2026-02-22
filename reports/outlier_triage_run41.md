# Outlier Triage Report - UDI run 41

Generated at: 2026-02-22 12:46:13 CST

## Scope
- source_run_id: `41`
- outlier threshold: `>100 DI / reg_no`
- total outlier reg_no: `16`
- sampling rule: each outlier reg_no sample first `10` DI rows from `udi_device_index`

## Type Definition
- Type A: `di_count >= 1000` (extreme concentration, highest risk, prioritize canonical checks)
- Type B: `200 <= di_count < 1000` (high concentration, queue review + keep quarantine)
- Type C: `100 <= di_count < 200` (moderate concentration, keep quarantine and observe)

## Distribution (run 41)
- Type A: `2`
- Type B: `7`
- Type C: `7`

## Top Outliers
| reg_no | di_count | type |
|---|---:|---|
| 国械注准20243131618 | 2582 | A |
| 国械注准20233130399 | 2234 | A |
| 苏械注准20242042183 | 412 | B |
| 国械注准20163161745 | 337 | B |
| 沪械注准20212040585 | 292 | B |
| 国械注准20223160393 | 277 | B |
| 国械注许20233160006 | 222 | B |
| 国械注准20213160200 | 216 | B |
| 国械注进20143165007 | 202 | B |
| 沪械注准20212040566 | 196 | C |

## Artifact
- CSV sample: `reports/outlier_triage_run41.csv`
- rows: `160` sampled records + header (16 outliers x 10 DI)

## Recommendation
1. Type A (`2` reg_no): **优先修 canonical/多证号映射**，完成前维持隔离，不建议放开 params 扩散。
2. Type B/C (`14` reg_no): **继续隔离可接受**，先不阻断主流程；人工抽检后把可接受项标记 `ignored/resolved` 再按需放开。
3. params 回充当前无增量，先补 allowlist（当前 `allowlisted_key_count=0`），否则扩大扫描也不会写入。
