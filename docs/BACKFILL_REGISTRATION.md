# Backfill: Registration Anchor (Normalize + Link)

本文件描述脚本 `scripts/backfill_registration_anchor.py` 的用途、参数、幂等性与回滚建议。

## 目标

在不改变业务口径的前提下，补齐“以 `registrations.registration_no` 为 canonical 主键”的锚定路径：

- 归一化：
  - `products.reg_no`
  - `product_variants.registry_no`
- 关联回填：
  - `products.registration_id` -> `registrations.id`
- 缺失注册证：当 `products.reg_no` 存在但 registrations 中没有对应注册证时，创建 `registrations` 行（`registration_no=normalized`）
- 对于 `product_variants.product_id` 已绑定的情况：尽量确保其指向的 product 具备 `registration_id`

归一规则 SSOT：
- `docs/NORMALIZE_KEYS.md`

## 使用方法

环境要求：
- 可访问 Postgres（使用与 API/Worker 相同的 `DATABASE_URL` 环境变量配置）
- 从 repo 根目录执行（或确保 `api/` 可被 import）

Dry-run（默认，不写入）：
```bash
./venv/bin/python scripts/backfill_registration_anchor.py --dry-run
```

Execute（幂等写入）：
```bash
./venv/bin/python scripts/backfill_registration_anchor.py --execute --batch-size 1000
```

参数：
- `--dry-run`：输出诊断信息（默认）
- `--execute`：执行写入（幂等）
- `--batch-size N`：execute 模式下每 N 行 commit（默认 1000）
- `--sample-limit N`：dry-run 样例输出数量（默认 20）

## Dry-run 输出说明

脚本会输出 JSON，包含：
- a) `products.reg_no` 非空但无法匹配 `registrations` 的数量与样例
- b) `products.registration_id` 为空但 `reg_no` 可匹配的数量
- c) `product_variants.registry_no` 可匹配 `registrations` 的数量
- d) `product_variants.registry_no` 与其绑定 product 的 `products.reg_no` 不一致的异常样例 TOP 50

额外输出（安全提示）：
- `registrations_norm_collisions`：若多个 `registrations.registration_no` 归一后落在同一个 key，会被标记为 collision；execute 模式会跳过此类 key 的回填以避免错误绑定。

## 写入与审计（change_log）

所有写入（normalize 写回、registration 创建、registration_id 回填）都会写入 `change_log`：
- `entity_type`：`product` / `product_variant` / `registration`
- `changed_fields`：字段级 old/new
- `before_json` / `after_json`：最小快照（与本 backfill 相关字段）
- `after_raw`：包含 `backfill=registration_anchor` 与时间戳

## 幂等性说明

重复执行 `--execute` 不会导致重复写入：
- 仅当归一化后的值与当前值不同才会更新
- `registrations` 仅在确实缺失 canonical key 时创建；若并发创建导致冲突，会 re-query 并继续
- `products.registration_id` 仅在为空且能确定唯一匹配时才回填

## 回滚建议

本脚本不提供自动回滚（因为涉及多表、可能与后续同步交织）。

建议回滚策略（按安全性优先级）：
1. 数据库级快照/备份回滚（推荐）
2. 基于 `change_log` 反向回放：
   - 过滤 `after_raw.backfill in ('registration_anchor', 'registration_anchor_from_variant')`
   - 按 `changed_at` 逆序，把字段恢复为 `changed_fields[field].old`
3. 若只想撤销 normalize（保留 registration_id）：可以只回滚 `reg_no` / `registry_no` 字段的变更。

注意：回滚前请评估是否已有新的 sync run 写入同一行，避免覆盖新数据。

