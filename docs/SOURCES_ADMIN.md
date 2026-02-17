# Sources Admin（Source Registry 配置系统）

## 目标
在不改现有抓取/解析逻辑的前提下，新增统一数据源配置系统：
- `source_definitions`：静态源定义（系统字典）
- `source_configs`：运行配置（后台可编辑）

## 数据模型
### 1) `source_definitions`（静态）
- `source_key`（PK），例：`NMPA_REG` / `UDI_DI` / `PROCUREMENT_GD` / `NHSA`
- `display_name`
- `entity_scope`（`REGISTRATION` / `UDI` / `PROCUREMENT` / `NHSA`...）
- `default_evidence_grade`（`A/B/C/D`）
- `parser_key`（代码 parser 标识）
- `enabled_by_default`

### 2) `source_configs`（运行）
- `id`（uuid PK）
- `source_key`（FK -> `source_definitions.source_key`，唯一）
- `enabled`
- `schedule_cron`（可空）
- `fetch_params`（jsonb）
- `parse_params`（jsonb）
- `upsert_policy`（jsonb）
- `last_run_at` / `last_status` / `last_error`

## Admin API
### GET `/api/admin/sources`
用途：查看全部源定义 + 当前运行配置（含最近运行状态）。

返回 `compat` 字段用于兼容旧系统：
- `bound`：是否已绑定到旧 `data_sources`
- `legacy_name` / `legacy_type`
- `legacy_exists` / `legacy_data_source_id` / `legacy_is_active`

### POST `/api/admin/sources`
用途：为某个 `source_key` 创建配置（首次）。

请求示例：
```json
{
  "source_key": "UDI_DI",
  "enabled": true,
  "schedule_cron": "0 */6 * * *",
  "fetch_params": {"page_size": 2000, "regions": ["GD", "ZJ"]},
  "parse_params": {"mapping_version": "v1"},
  "upsert_policy": {"priority": 20, "conflict": "grade_priority_time", "allow_overwrite": false}
}
```

如需无代码接入旧 worker（兼容旧 `data_sources`），在 `fetch_params` 增加：
```json
{
  "legacy_data_source": {
    "name": "广东集采增强源",
    "type": "postgres",
    "role": "supplement",
    "config": {
      "host": "db",
      "port": 5432,
      "database": "nmpa",
      "username": "nmpa",
      "password": "****",
      "source_table": "public.procurement_results"
    }
  }
}
```
- `role=primary`：可作为主源（`enabled=true` 时会激活该 `data_sources`）
- `role=supplement`：作为增强源，不抢占主源

### PATCH `/api/admin/sources`
用途：更新配置（启停、参数、最近运行状态）。

请求示例：
```json
{
  "source_key": "UDI_DI",
  "enabled": false,
  "fetch_params": {"page_size": 1000},
  "upsert_policy": {"priority": 10, "allow_overwrite": false}
}
```

## 参数优先级（必须遵守）
为避免“显示值和实际执行值不一致”，`fetch_params` 统一按以下顺序生效：
1. 顶层 `fetch_params.*`（权威口径）
2. `fetch_params.legacy_data_source.config.*`（兼容回退）
3. 系统默认值

适用关键参数：
- `batch_size`
- `cutoff_window_hours`
- `source_query`
- `source_table`
- 连接参数（`host/port/database/username/password/sslmode`）

建议：顶层仅放“运行控制参数”，nested 仅放“连接与源表信息”，并保持同名参数一致。

## 新增一个数据源的步骤
1. 直接调用 `POST /api/admin/sources`：
   - 若 `source_key` 不存在，可同时提交 `display_name/entity_scope/parser_key` 自动创建定义。
2. 在 `fetch_params` 写入抓取参数；如需兼容旧 worker，补 `legacy_data_source` 区块。
3. 通过 `PATCH /api/admin/sources` 调整启停、参数、策略。
4. 通过 `GET /api/admin/sources` 观察 `last_*` 与 `compat.*`。

推荐最小模板（PostgreSQL 源）：
```json
{
  "source_key": "NMPA_REG",
  "enabled": true,
  "schedule_cron": "0 */6 * * *",
  "fetch_params": {
    "batch_size": 2000,
    "cutoff_window_hours": 6,
    "legacy_data_source": {
      "name": "NMPA注册产品库（主数据源）",
      "type": "postgres",
      "role": "primary",
      "config": {
        "host": "db",
        "port": 5432,
        "database": "nmpa",
        "username": "nmpa",
        "password": "***",
        "source_table": "public.products",
        "source_query": "SELECT * FROM public.products WHERE updated_at >= :cutoff ORDER BY updated_at DESC LIMIT :batch_size"
      }
    }
  },
  "parse_params": {"mapping_version": "v1"},
  "upsert_policy": {"priority": 100, "conflict": "evidence_then_priority", "allow_overwrite": true}
}
```

## 启用/停用
- 启用：`PATCH /api/admin/sources`，`enabled=true`
- 停用：`PATCH /api/admin/sources`，`enabled=false`

## 回滚
若需回滚本次能力：
1. 执行：`scripts/rollback/0030_add_source_registry_down.sql`
2. 表会移除：`source_configs`、`source_definitions`
3. 不影响现有 `data_sources` 与已有抓取逻辑

## 兼容性说明
- 现有 worker/sync 抓取逻辑保持不变。
- 通过 `fetch_params.legacy_data_source` 可把 Source Registry 配置桥接到旧 `data_sources`，实现统一后台管理。
- 对于新增来源，优先走 Source Registry；仅在需要兼容旧链路时补 `legacy_data_source`，通常无需改后端代码。
- 系统会在配置同步阶段把顶层关键参数覆盖到 legacy 侧，确保“后台配置”和“运行时读取”一致。
