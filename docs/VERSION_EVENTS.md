# Registration Version Events (Productized Consumption)

目的：在不改变既有 `nmpa_snapshots/field_diffs` SSOT 的前提下，新增 `registration_events` 作为“版本事件表”，方便产品化消费（日指标/订阅/日报/预警）直接按事件流处理。

## 表结构

新增表：`registration_events`
- `id` uuid pk
- `registration_id` uuid fk -> `registrations.id`（index）
- `event_type` text：`INITIAL/CHANGE/RENEWAL/CANCEL/UNKNOWN`
- `event_date` date：用于日指标窗口（当前取 `nmpa_snapshots.snapshot_date`）
- `summary` text：短摘要
- `source_run_id` bigint fk -> `source_runs.id` nullable
- `snapshot_id` uuid fk -> `nmpa_snapshots.id` nullable
- `created_at` timestamptz

幂等键：
- `UNIQUE(registration_id, source_run_id, event_type)`（同一注册证同一 run 的同类事件不重复）

迁移：
- `migrations/0025_add_registration_events.sql`

回滚：
- `scripts/rollback/0025_add_registration_events_down.sql`

## 生成任务（CLI）

命令：
- dry-run：
  - `python -m app.workers.cli registration:events --dry-run --date YYYY-MM-DD`
  - `python -m app.workers.cli registration:events --dry-run --since YYYY-MM-DD`
- execute：
  - `python -m app.workers.cli registration:events --execute --date YYYY-MM-DD`
  - `python -m app.workers.cli registration:events --execute --since YYYY-MM-DD`

输入依据：
- `field_diffs`（字段集合严格来自 SSOT 的 `diff_fields`）
- `registrations.status/expiry_date`（用于 CANCEL 的兜底判断）

输出副作用（execute）：
- upsert `registration_events`
- 同步写入 `change_log`（`entity_type='registration'`）用于订阅/日报复用

## 规则（V1）

字段集合（来自 SSOT `diff_fields`）：
- `registration_no`
- `filing_no`
- `approval_date`
- `expiry_date`
- `status`
- `product_name`
- `class`
- `model`
- `specification`

事件类型判定（优先级从高到低）：
1. `INITIAL`
   - 若该 `registration_id` 在当前 snapshot 之前没有更早的 `nmpa_snapshots`（按 `snapshot_date` 比较）则为 INITIAL
2. `CANCEL`
   - 若 `field_diffs` 中 `status` 的 `new_value` 归一后为 `cancelled`
   - 或 `registrations.status` 归一后为 `cancelled`（兜底）
3. `RENEWAL`
   - 若 `expiry_date` 的新值是合法日期且 `new > old`
4. `CHANGE`
   - 其余存在任何 diff 的情况
5. `UNKNOWN`
   - 无 diff 且不满足其它条件（保留扩展空间）

summary（摘要）规则：
- INITIAL：`initial snapshot`
- CANCEL：`status cancelled`
- RENEWAL：`expiry_date extended`
- CHANGE：`changed: <diff_fields...>`（最多 8 个字段）

## 注意事项

- 本 V1 规则是“可解释、可迭代”的基线；后续可引入更精细的规则（例如 status 的更多枚举、renewal 判定增强、事件合并等），但不应回写/破坏已有 SSOT。
- `change_log` 不做 dedup（目前以 `registration_events` 的幂等为准：只有插入新 event 时才写 change_log）。

