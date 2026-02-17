# 字段级冲突策略（Conflict Policy）

## 目标
在不改变现有 IVD 展示口径的前提下，确保结构化写入遵循统一锚点与可追溯原则：

- 唯一锚点：`registrations.registration_no`（canonical key）
- 所有源先归一到 `registration_no`，再写结构化表
- UDI `di` 仅为规格/包装层补充实体，挂在 `registration_no` 下
- 覆盖必须可追溯：`raw_source_record_id/raw_id + change_log`

## 自动裁决顺序（字段级）
对 `registrations` 合同字段（当前：`filing_no/approval_date/expiry_date/status`）写入时：

1. `evidence_grade`：`A > B > C > D`
2. 同 grade 比 `source_priority`：数值越小优先级越高
3. 同优先级比 `observed_at`：更新（更新鲜）覆盖旧值

实现位置：
- `api/app/services/source_contract.py::apply_field_policy`
- `api/app/services/source_contract.py::upsert_registration_with_contract`
- `api/app/services/ingest.py::upsert_product_record`

## 无法自动裁决（入队）
若出现同字段“同 grade + 同 priority + 同 observed_at + 值不同”，不自动覆盖，写入：

- `conflicts_queue`（`status='open'`）
- `registration_conflict_audit`（`resolution='REJECTED'`, `reason='same_grade_priority_time_requires_manual'`）

`conflicts_queue` 关键字段：
- `registration_no`, `field_name`
- `candidates`（`source_key/value/raw_id/observed_at/evidence_grade/source_priority`）
- `status`（`open/resolved`）
- `winner_value`, `winner_source_key`, `resolved_by`, `resolved_at`

## 人工处理接口（最小）

1. 查询冲突队列  
`GET /api/admin/conflicts?status=open|resolved|all&limit=...`

2. 人工裁决  
`POST /api/admin/conflicts/{id}/resolve`

请求体示例：

```json
{
  "winner_value": "ACTIVE",
  "winner_source_key": "MANUAL"
}
```

处理效果：
- 更新 `registrations.<field_name>`
- 更新 `registrations.raw_json._contract_provenance`
- 写 `change_log`（`entity_type='registration'`，包含 before/after 与 `source_key`）
- 将队列项置为 `resolved`

兼容说明：
- 旧路径 `/api/admin/conflicts-queue` 与 `/api/admin/conflicts-queue/{id}/resolve` 仍可用。

## 迁移与回滚

- 迁移：`migrations/0032_add_conflicts_queue.sql`
- 回滚：`scripts/rollback/0032_add_conflicts_queue_down.sql`

## 注意
- 当前策略是“注册证主实体字段”的冲突裁决；衍生实体（价格/集采/方法学）可复用同规则，但建议分实体单独建队列。
- `source_priority` 口径必须在配置与文档中保持一致（本项目为“小值优先”）。
