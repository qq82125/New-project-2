# IVD 数据源增强运行手册

## 前置
- 数据库迁移：
  - `python -m app.db.migrate`
- 启动 API/Worker：
  - `docker compose up -d --build`

## 1) 运行一次 UDI 同步
```bash
python -m app.cli source:udi --date 2026-02-13 --mode execute
```

## 2) 全量分类回填（先 dry-run 再 execute）
```bash
python -m app.cli ivd:classify --version ivd_v1_20260213 --mode dry-run
python -m app.cli ivd:classify --version ivd_v1_20260213 --mode execute
```

## 3) 非IVD清理（先 dry-run 再 execute）
```bash
python -m app.cli ivd:cleanup --mode dry-run
python -m app.cli ivd:cleanup --mode execute
```

- `execute` 输出中会包含归档批次标识（`archive_batch_id=...`）并写入 `data_cleanup_runs.notes`。

## 4) 回滚
```bash
python -m app.cli ivd:rollback --mode execute --archive-batch-id <batch_id>
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
