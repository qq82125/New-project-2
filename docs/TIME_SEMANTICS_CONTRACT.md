# TIME_SEMANTICS_CONTRACT

## 目标
统一“注册证新增时间（start_date）”口径，避免 signals 计算出现“入库新增”和“监管新增”混用导致的漂移。

本契约适用于：
- track competition 的 `new_rate_12m`
- company growth 的 `new_registrations_12m` / `new_tracks_12m` / `growth_slope` 的新增分量

## 自动字段适配
系统在运行时通过 SQLAlchemy inspector 检测真实 schema（而非硬编码字段）：
- `registrations`
- `nmpa_snapshots`（若存在）
- `registration_events`（若存在）
- `products`（若存在）

仅在表/列存在时才参与口径计算，不存在则自动跳过并进入下一优先级。

## start_date 口径优先级（高 -> 低）

### 优先级 1：监管批准/生效时间
- `registrations.approved_at`
- `registrations.approval_date`
- `registrations.approved_date`

说明：这是最接近监管“生效/批准”的时间语义，优先使用。

### 优先级 2：系统首次观测（快照）
- `MIN(nmpa_snapshots.snapshot_date|snapshot_at|observed_at|created_at)`（按 registration 维度）

说明：用于补齐缺失批准日期时的“首次被系统看到”时间。

### 优先级 3：事件链首次 create/issue/approve
- `MIN(registration_events.event_date|observed_at|created_at)`，事件类型限定 create/issue/approve 语义

说明：当快照不可用时，用事件链近似监管生效时点。

### 优先级 4：产品侧近似
- `MIN(products.approved_at|approved_date)`（按 registration 关联）

说明：仅在 registration 主线缺失时使用，避免直接退化到入库时间。

### 优先级 5：兜底入库时间
- `registrations.created_at`

说明：最后兜底，不代表监管批准时间。

## 统一函数
- `get_registration_start_date(db, registration_no, as_of_date) -> (date|None, source_key)`
- `get_registration_start_date_map(db, as_of_date, registration_nos=None) -> (map, source_stats)`

`source_key` 用于 explainability，例如：
- `registrations.approval_date`
- `nmpa_snapshots.first_observed`
- `registration_events.first_create_issue_approve`
- `products.approved_date`
- `registrations.created_at`
- `missing`

## 对 signals 的影响

### Track（competition）
- `new_rate_12m = 新增数 / total_count`
- 新增定义：`start_date` 落在 `[as_of_date-12m, as_of_date]`
- factor explanation 中必须携带 source 分布（例如 approval/snapshot 占比）与 missing 数量

### Company（growth）
- `new_registrations_12m`、`new_tracks_12m` 的“新增”同样使用 `start_date`
- 公司归属（registration -> company）可继续沿用现有 anchor 逻辑；仅时间口径统一

## approval_date 与 first_seen/observed_at 的使用边界
- 有批准日期时：用批准日期（监管语义优先）
- 批准日期缺失时：才回退到 snapshot/event 的 first seen
- created_at 仅兜底，不可作为默认“新增时间”

## 常见误用
- 误用 1：把 `registrations.created_at` 当作监管新增
  - 后果：new_rate_12m 会被“批量导入时间”污染，出现异常集中
- 误用 2：track 用 approval_date，company 用 created_at
  - 后果：页面间口径不一致，track/company 同期新增无法对齐
- 误用 3：忽略 source_key 覆盖率
  - 后果：当 `missing` 占比高时无法解释趋势跳变风险
