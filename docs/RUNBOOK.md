# IVD 数据源增强运行手册

## 前置
- 数据库迁移：
  - `python -m app.db.migrate`
- 启动 API/Worker：
  - `docker compose up -d --build`

## Rollback 脚本覆盖校验（建议 CI/发布前必跑）
确保每个 `migrations/*.sql`（默认从 0011 开始）都有对应的 `scripts/rollback/*_down.sql`。
```bash
python3 scripts/verify_rollback_coverage.py
```

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

## Pending 队列写入模式（缺 registration_no 时）

环境变量：`PENDING_QUEUE_MODE`
- `both`（默认）：同时写 `pending_records`（行级）与 `pending_documents`（文档级）
- `document_only`：只写 `pending_documents`（避免重复积压口径）
- `record_only`：只写 `pending_records`（兼容旧口径）

## pending_records Schema Guard（0031 口径）

用于确保任意环境中的 `pending_records` 符合 `migrations/0031_add_pending_records.sql`：
- `status` 默认值为 `open`
- `chk_pending_records_status` 允许 `open/resolved/ignored/pending`
- `uq_pending_records_run_payload` 唯一保护存在
- 关键索引存在：`idx_pending_records_status`、`idx_pending_records_source_key`

运行命令（本地）：
```bash
DATABASE_URL=postgresql+psycopg://nmpa:nmpa@127.0.0.1:5432/nmpa python scripts/verify_schema_pending_records.py
```

CI/发布前建议将此脚本作为必跑校验项；若不符合会返回非 0 并打印具体缺项。

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

## Admin Pending 手工验收（PR-F1）

启动：
```bash
docker compose up -d --build
```

验收步骤（浏览器）：
1. 打开 `http://localhost:3000/admin/pending`
2. 点击任意一行或“查看详情”，弹出详情窗口
3. 确认详情字段展示完整：
   - `candidate_product_name/candidate_company/candidate_registry_no`
   - `raw_document_id/source_key/reason_code/created_at`
4. Resolve 流程：
   - 输入 `registration_no`
   - 点击 `Resolve`
   - 成功后窗口关闭，列表和统计自动刷新
5. Ignore 流程：
   - 输入可选 `reason`
   - 点击 `Ignore`
   - 成功后窗口关闭，列表和统计自动刷新
6. 错误展示：
   - 触发失败时，窗口内必须显示后端返回的 `code/message/detail`
   - toast 同步显示同一错误内容（不是泛化“失败”提示）

说明：
- 若后端环境尚未提供 `/api/admin/pending/{id}/ignore`，前端会展示后端原始错误信息（通常为 404 或 detail）。

## Admin Conflicts 手工验收（PR-F2）

启动：
```bash
docker compose up -d --build
```

验收步骤（浏览器）：
1. 打开 `http://localhost:3000/admin/conflicts`
2. 默认视图应为 `grouped`，可切换到 `raw-list`
3. grouped 模式：
   - 按 `registration_no` 分组展示
   - 每组可看到 `field_name` 与 `candidates`
4. resolve 必填 reason：
   - 不填写 reason 点击裁决，应提示 `E_REASON_REQUIRED`（或后端同类错误）
   - 填写 `winner_value + reason` 后裁决成功，列表自动刷新
5. 失败提示：
   - 页面内错误行显示后端返回 `code/message/detail`
   - toast 显示相同错误信息

## Admin Sources 手工验收（PR-F3）

启动：
```bash
docker compose up -d --build
```

验收步骤（浏览器）：
1. 打开 `http://localhost:3000/admin/sources`
2. 页面应展示 Source 列表，且包含字段：
   - `source_key/display_name/entity_scope`
   - `parser_key/default_evidence_grade/priority/enabled`
3. 点击任意一条 `编辑`，在弹层修改以下任一字段并保存：
   - `enabled`
   - `schedule_cron`
   - `upsert_policy.priority`
   - `parse_params.parser_key`
   - `parse_params.default_evidence_grade`
4. 保存成功后：
   - 弹层关闭
   - 列表自动刷新并展示最新值
5. 失败路径验证：
   - 输入非法值（例如 `priority` 非数字）触发前端校验
   - 或制造后端失败，确认页面与 toast 均显示后端 `code/message/detail`

回滚方式：
```bash
git restore --source=HEAD~1 web/app/admin/sources/page.tsx web/components/admin/SourcesRegistryManager.tsx docs/RUNBOOK.md
```
