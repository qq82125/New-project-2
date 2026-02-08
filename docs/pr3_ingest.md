# PR3 数据解析、Upsert、变更检测

## 目标
- 将 staging 记录映射到 `products` 标准字段 + `raw`
- 执行 upsert
- 生成 `change_log`（`new` / `update` / `cancel` / `expire`）
- 回写 `source_runs` 统计（`added/updated/removed`）

## 关键实现
- 统一模型：`/Users/GY/Documents/New project 2/api/app/services/mapping.py`
  - `ProductRecord` dataclass
- 字段映射与状态标准化：`map_raw_record`
- Upsert + diff：`/Users/GY/Documents/New project 2/api/app/services/ingest.py`
  - diff 字段：`status/expiry_date/approved_date/company_id/name/reg_no/udi_di/class`
  - `changed_fields` 结构：`{"field": {"old": ..., "new": ...}}`
- source_runs 统计扩展：
  - `added_count/updated_count/removed_count`
  - 迁移：`/Users/GY/Documents/New project 2/migrations/0004_pr3_ingest_columns.sql`

## 注意
- 本 PR 不包含 Dashboard 聚合
- 本 PR 不包含订阅逻辑
- 本 PR 不包含前端改动
