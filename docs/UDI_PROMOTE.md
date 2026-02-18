# UDI 规格索引提升（udi:promote）

本步骤用于把 `udi_device_index` 中的记录按 `registration_no_norm` 回写到注册证主实体，完成 UDI 数据从“原始索引”向“可消费结构化”落地。

## 目标口径

- `di`（UDI 规格码）仍为规格层唯一键，先保留在 `product_variants`。
- 有 `registration_no` 的记录按以下顺序执行：
  1. `normalize_registration_no`
  2. 先 `upsert registrations`
  3. 再创建/更新 `products`（低门槛 stub，`status=UNKNOWN`）
  4. 回填 `product_variants.registry_no` 与 `product_variants.product_id`
  5. 写入 `product_udi_map(registration_no, di, match_type='direct', confidence=0.95)`
- 无 `registration_no` 的记录只保留 `product_variants` 与 `pending_records`，避免污染注册证锚点。
- 注册证/产品层标记（Stub）：
  - `registrations.raw_json._stub` 与 `products.raw_json._stub`
  - `evidence_level=LOW`
  - `source_hint='UDI'`
  - `verified_by_nmpa=false`

## 命令

### 只预览（dry-run）

```bash
venv/bin/python -m app.workers.cli udi:promote --source-run-id <source_run_id> --limit 200
```

说明：未显式传 `--execute` 时自动 dry-run（`source-run-id` 可选，也可用 `--raw-document-id` 做单文件筛选）。

### 真正落库（execute）

```bash
venv/bin/python -m app.workers.cli udi:promote --execute --source-run-id <source_run_id> --limit 200
```

结果会返回结构化汇总：

- `scanned`
- `with_registration_no`
- `missing_registration_no`
- `promoted`
- `registration_created`
- `registration_updated`
- `product_created`
- `product_updated`
- `variant_upserted`
- `map_upserted`
- `pending_written`
- `skipped_no_di`
- `failed`
- `errors[]`

## 前端校验（默认不展示待核验）

所有公测/公开列表默认隐藏待核验项；如需显示：

- 搜索：`/search?include_unverified=true`
- 仓库库（library）：`/library?include_unverified=true`

命中 `product.raw_json._stub` 的条目会显示 Badge：

- `UDI来源｜待NMPA核验`

## 后续人工处理入口

- 无 `registration_no` 的 DI 可在 pending 管理界面处理（依据现有 pending/pending_documents 工作流）。
- 已绑定的 UDI 记录也会在细节页保留其 stub 标记，避免被误当作 NMPA 官方权威字段直接消费。

## 回滚/安全说明

- 本命令对 `product_udi_map`、`product_variants`、`product_udi_map`、`registrations`、`products` 为 upsert/幂等写入；
- 重复执行 `--execute` 不应产生重复主键冲突（`di`、`registration_no`/`product_udi_map` 使用唯一约束或 upsert 保护）；
- 若需要回滚，请按对应迁移的回滚脚本回退新增结构，或通过管理侧逐步取消映射并清理 stub 记录。

## 执行快照（脚本）

为便于日常运维做成功率核对，可直接运行：

```bash
python -m app.workers.cli udi:promote-snapshot --source-run-id 123 --limit 200
```

或在项目根目录（保持旧流程）运行：

```bash
python scripts/udi_promote_snapshot.py --source-run-id 123 --limit 200
```

或在 api 容器内直接运行（文件已随镜像同步）：

```bash
docker compose exec -T api python3 /app/api/scripts/udi_promote_snapshot.py --source-run-id 123 --limit 200
```

参数：

- `--source-run-id`：按 `source_runs.id` 过滤（可选）
- `--raw-document-id`：按 `raw_document_id` 过滤（可选）
- `--source`：写入路径标识，默认 `UDI_PROMOTE`（可选）
- `--limit`：扫描上限（可选）
- `--execute`：缺省为 dry-run（不落库）；加上 `--execute` 才会写库

输出样例（JSON）包含：

- 继承 `udi:promote` 的原始计数字段（`scanned`、`with_registration_no`、`missing_registration_no`、`pending_written`、`errors` 等）
- `snapshot.metrics` 中的成功率：
  - `promoted_rate_pct`
  - `reg_no_hit_rate_pct`
  - `pending_rate_pct`
  - `failure_rate_pct`
