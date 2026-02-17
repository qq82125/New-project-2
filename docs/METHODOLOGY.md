# Methodology Tree (V1) & Registration Mapping

目标：提供方法学树（V1）与注册证映射能力，用于后续“赛道/方法学维度”的检索、指标、风险判断。

## 1) 数据表

### `methodology_nodes`
树结构节点（支持同义词）。
- `id` uuid pk
- `name` text
- `parent_id` uuid nullable -> `methodology_nodes.id`
- `level` int
- `synonyms` jsonb（数组，字符串列表）
- `is_active` boolean
- `created_at`/`updated_at`

迁移：
- `migrations/0023_add_methodology_nodes.sql`

回滚：
- `scripts/rollback/0023_add_methodology_nodes_down.sql`

### `registration_methodologies`
注册证与方法学多对多映射（允许多条）。
- `id` uuid pk
- `registration_id` uuid fk -> `registrations.id`（index）
- `methodology_id` uuid fk -> `methodology_nodes.id`（index）
- `confidence` numeric(3,2)
- `source` text（rule/manual）
- `created_at`/`updated_at`

约束：
- `UNIQUE(registration_id, methodology_id)` 防止重复插入同一对

迁移：
- `migrations/0024_add_registration_methodologies.sql`

回滚：
- `scripts/rollback/0024_add_registration_methodologies_down.sql`

## 2) Seeds

方法学树 V1 seeds：
- `docs/methodology_tree_v1.json`

覆盖（示例集合）：
- PCR / qPCR / dPCR
- NGS（含 WGS/WES/Panel）
- CLIA / ELISA
- POCT（含 POCT-PCR/POCT-免疫）
等

## 3) 规则映射任务（CLI）

### 3.1 Seed 写入（建议先做）
```bash
python -m app.workers.cli methodology:seed --execute --file docs/methodology_tree_v1.json
```

Dry-run：
```bash
python -m app.workers.cli methodology:seed --dry-run --file docs/methodology_tree_v1.json
```

### 3.2 Rule Map（写 registration_methodologies）
规则来源（V1）：
- `registrations.raw_json`（全文关键词）
- `products.name`（按 `registration_id` 或 `products.reg_no == registration_no` 关联）
- `product_params`（按 `registry_no == registration_no`；拼接 `param_code + value_text`）

执行（全量）：
```bash
python -m app.workers.cli methodology:map --execute
```

仅对指定注册证：
```bash
python -m app.workers.cli methodology:map --execute --registration-no REG001 --registration-no REG002
```

Dry-run：
```bash
python -m app.workers.cli methodology:map --dry-run
```

## 4) Admin API（最小）

获取某注册证的映射：
- `GET /api/admin/registrations/{registration_no}/methodologies`

手工增删改（upsert + delete）：
- `POST /api/admin/registrations/{registration_no}/methodologies`

payload 示例：
```json
{
  "items": [
    {"methodology_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "confidence": 0.95, "source": "manual"}
  ],
  "delete_methodology_ids": [
    "ffffffff-1111-2222-3333-444444444444"
  ]
}
```

说明：
- `source` 允许 `rule/manual`
- `confidence` 会被 clamp 到 `[0,1]`

