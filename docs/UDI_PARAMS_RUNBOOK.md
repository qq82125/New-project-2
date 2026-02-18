# UDI Params Runbook (Batch/Resume/Recover)

## 目标
在 `udi_device_index`（当前约 5,380,928 行）上稳定执行 `udi:params`，实现：
- A 管线：allowlist 参数写入 `product_params`（可分批、可断点恢复）
- B 管线：候选字段统计写入 `param_dictionary_candidates`（默认抽样，2-3 分钟级）

## 一、A 管线（必须）

### 1) 标准执行（允许中断后续跑）
```bash
docker compose exec worker python -m app.workers.cli udi:params \
  --execute \
  --only-allowlisted \
  --batch-size 50000 \
  --resume
```

### 2) 关键行为
- 游标字段：`udi_device_index.di_norm`（升序）
- 每批流程：
  1. 读一批可绑定 `registrations -> products(is_ivd=true)` 的记录
  2. 只生成 allowlist 参数：
     - `STORAGE`（`storage_json.storages`）
     - `STERILIZATION_METHOD`（`mjfs`）
     - `SPECIAL_STORAGE_COND`（`tscchcztj`）
     - `SPECIAL_STORAGE_NOTE`（`tsccsm`）
     - `LABEL_LOT` / `LABEL_SERIAL_NO` / `LABEL_PROD_DATE` / `LABEL_EXP_DATE`
  3. 以 `(product_id, param_code)` 为键做批次 upsert（`extract_version='udi_params_allowlist_v1'`）
  4. 提交事务并更新 checkpoint

### 3) 断点恢复
- checkpoint 表：`udi_jobs_checkpoint`
- job key：
  - 全量：`udi:params:allowlist`
  - 按 `source_run_id`：`udi:params:allowlist:srid:<id>`
- 常用命令：
```bash
# 从 checkpoint 继续（默认）
docker compose exec worker python -m app.workers.cli udi:params --execute --only-allowlisted --resume

# 忽略 checkpoint，从头开始
docker compose exec worker python -m app.workers.cli udi:params --execute --only-allowlisted --no-resume

# 指定起始游标（覆盖 checkpoint）
docker compose exec worker python -m app.workers.cli udi:params --execute --only-allowlisted --start-cursor 0694...
```

### 4) 批次日志
每批会输出：
- `rows_scanned`
- `rows_written`
- `elapsed_ms`
- `cursor`

完成汇总输出：
- `total_written`
- `distinct_products_updated`
- `final_cursor`
- `total_batches`

## 二、B 管线（候选统计，默认抽样）

### 1) 默认 dry-run（推荐）
```bash
docker compose exec worker python -m app.workers.cli udi:params \
  --dry-run \
  --sample-limit 200000 \
  --top 50
```

行为：
- 抽样扫描 `udi_device_index`（默认 200k 行）
- 输出 top50 非空字段与空值率
- 同时 upsert 到 `param_dictionary_candidates`
- `sample_meta` 记录抽样参数与样本口径：
  - `sampled_rows`
  - `sample_storage_present_rows`
  - `sample_packing_present_rows`

### 2) 全量统计（默认关闭）
```bash
docker compose exec worker python -m app.workers.cli udi:params --dry-run --full-scan --top 50
```
说明：
- 非 `--full-scan` 时不输出 global 计数
- `--full-scan` 时输出：
  - `global_storage_present_rows`
  - `global_packing_present_rows`

## 三、验收 SQL

```sql
-- allowlist 写入规模（目标：至少几万级）
SELECT COUNT(*)
FROM product_params
WHERE extract_version = 'udi_params_allowlist_v1';

-- 覆盖产品数
SELECT COUNT(DISTINCT product_id)
FROM product_params
WHERE extract_version = 'udi_params_allowlist_v1'
  AND product_id IS NOT NULL;

-- 按参数键覆盖
SELECT param_code, COUNT(*) AS rows, COUNT(DISTINCT product_id) AS products
FROM product_params
WHERE extract_version = 'udi_params_allowlist_v1'
GROUP BY param_code
ORDER BY rows DESC;

-- checkpoint
SELECT job_name, cursor, updated_at
FROM udi_jobs_checkpoint
ORDER BY updated_at DESC;

-- storage 口径复核（请求的顺手检查）
SELECT COUNT(*)
FROM udi_device_index
WHERE storage_json IS NOT NULL
  AND storage_json::text <> '[]';

-- STORAGE 质量抽样（min<max）
SELECT COUNT(*) AS ok_rows
FROM product_params
WHERE extract_version = 'udi_params_allowlist_v1'
  AND param_code = 'STORAGE'
  AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(COALESCE(conditions->'storages', '[]'::jsonb)) AS s
      WHERE (s->>'min') ~ '^-?[0-9]+(\\.[0-9]+)?$'
        AND (s->>'max') ~ '^-?[0-9]+(\\.[0-9]+)?$'
        AND ((s->>'min')::numeric < (s->>'max')::numeric)
  );

-- STORAGE 质量抽样（单位含 ℃）
SELECT COUNT(*) AS unit_c_rows
FROM product_params
WHERE extract_version = 'udi_params_allowlist_v1'
  AND param_code = 'STORAGE'
  AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(COALESCE(conditions->'storages', '[]'::jsonb)) AS s
      WHERE COALESCE(s->>'unit', '') = '℃'
  );
```

## 四、异常恢复建议
- 若单批超时：降低 `--batch-size`（如 20000 / 10000）
- 若中途终止：直接重跑并保留 `--resume`
- 若需要对某段重算：使用 `--start-cursor`
- 若需要候选统计但要快：优先 `--sample-limit`，避免 `--full-scan`
