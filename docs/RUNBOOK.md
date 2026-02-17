# IVD 数据源增强运行手册

## 前置
- 数据库迁移：
  - `python -m app.db.migrate`
- 启动 API/Worker：
  - `docker compose up -d --build`

## 1) 运行一次 UDI 同步
```bash
python -m app.cli source:udi --date 2026-02-13 --execute
```

## 2) 全量分类回填（先 dry-run 再 execute）
```bash
python -m app.cli ivd:classify --version ivd_v1_20260213 --dry-run
python -m app.cli ivd:classify --version ivd_v1_20260213 --execute
```

## 3) 非IVD清理（先 dry-run 再 execute）
```bash
python -m app.cli ivd:cleanup --dry-run --archive-batch-id non_ivd_cleanup_preview_$(date -u +%Y%m%d%H%M%S)
python -m app.cli ivd:cleanup --execute --archive-batch-id non_ivd_cleanup_$(date -u +%Y%m%d%H%M%S)
```

- 为了可回滚可追溯，`--execute` 必须显式提供 `--archive-batch-id`。
- dry-run 输出会包含分布统计（例如按 `raw_json.source`/`raw.source`、按 `created_at` 月份）。
- 执行后 `archive_batch_id` 会写入 `products_archive.archive_batch_id` 与 `change_log_archive.archive_batch_id`。

## 4) 回滚
```bash
python -m app.cli ivd:rollback --execute --archive-batch-id <batch_id>
```
可选：回滚后重算多少天指标（默认 365 天）：
```bash
python -m app.cli ivd:rollback --execute --archive-batch-id <batch_id> --recompute-days 365
```

## 5) 指标重算
```bash
python -m app.cli metrics:recompute --scope ivd --since 2026-01-01
```

## 口径说明
- 主产品查询口径：`products.is_ivd = true`
- 非 IVD 同步数据：不写主表，可写入 `products_rejected` 审计
- 破坏性清理：始终“先归档到 `products_archive` 再删除”

## 证据链表
- `raw_documents`：原始文档元数据（`storage_uri`, `sha256`, `run_id`, `source_url`）
- `product_params`：参数与证据（`evidence_text`, `evidence_page`, `raw_document_id`）

## NMPA 快照与字段级 diff（shadow-write）

新增表（用于订阅/日报/预警逐步接入，不改变现有前台口径）：
- `nmpa_snapshots`：注册证快照索引（每次 run 每注册证 1 条）
- `field_diffs`：字段级 diff（old/new），字段集合见 SSOT

SSOT：
- `docs/NMPA_FIELD_DICTIONARY_V1_ADAPTED.md`
- `docs/nmpa_field_dictionary_v1_adapted.yaml`

查看快照数量/异常（since）：
```bash
python -m app.cli nmpa:snapshots --since 2026-02-01
```

查看当天 diff 摘要（供 daily-digest 逐步接入）：
```bash
python -m app.cli nmpa:diffs --date 2026-02-08
```
