# PR1 Schema (PostgreSQL 15+)

本文件描述 `NMPA IVD 注册情报看板` 的数据库基础层（仅 PR1）。

## 目标
- 稳定、可扩展的数据模型
- 支持模糊搜索（`pg_trgm`）与 Dashboard 聚合
- Migration 可重复执行（幂等）

## 表结构

### 1) `companies`
- `id` `uuid` PK
- `name` `varchar(255)` UNIQUE, NOT NULL
- `country` `varchar(80)` NULL
- `raw` `jsonb` NOT NULL
- `created_at` `timestamptz` NOT NULL
- `updated_at` `timestamptz` NOT NULL

关系：
- `products.company_id -> companies.id`
- `subscriptions.company_id -> companies.id`

### 2) `products`
- `id` `uuid` PK
- `company_id` `uuid` FK -> `companies(id)`
- `name` `varchar(500)` NOT NULL
- `reg_no` `varchar(120)` NULL
- `udi_di` `varchar(128)` NOT NULL
- `status` `varchar(20)` NOT NULL
- `approved_date` `date` NULL
- `expiry_date` `date` NULL
- `raw` `jsonb` NOT NULL
- `created_at` `timestamptz` NOT NULL
- `updated_at` `timestamptz` NOT NULL

备注：`raw/reg_no/udi_di/status/approved_date/expiry_date` 为强制字段。

### 3) `source_runs`
- `id` `bigserial` PK
- `source` `varchar(80)` NOT NULL
- `run_type` `varchar(30)` NOT NULL
- `status` `varchar(20)` NOT NULL
- `message` `text` NULL
- `started_at` `timestamptz` NOT NULL
- `finished_at` `timestamptz` NULL
- `created_at` `timestamptz` NOT NULL

### 4) `change_log`
- `id` `bigserial` PK
- `product_id` `uuid` FK -> `products(id)`
- `source_run_id` `bigint` FK -> `source_runs(id)`
- `change_type` `varchar(20)` NOT NULL
- `changed_fields` `jsonb` NOT NULL
- `before_raw` `jsonb` NULL
- `after_raw` `jsonb` NULL
- `change_date` `timestamptz` NOT NULL

备注：`change_type/changed_fields/change_date` 为强制字段。

### 5) `subscriptions`
- `id` `bigserial` PK
- `company_id` `uuid` FK -> `companies(id)`
- `subscription_type` `varchar(30)` NOT NULL
- `target_value` `varchar(255)` NOT NULL
- `webhook_url` `text` NULL
- `is_active` `boolean` NOT NULL
- `last_digest_date` `date` NULL
- `created_at` `timestamptz` NOT NULL
- `updated_at` `timestamptz` NOT NULL

### 6) `daily_metrics`
- `metric_date` `date` PK（一天一行）
- `new_products` `int` NOT NULL
- `updated_products` `int` NOT NULL
- `cancelled_products` `int` NOT NULL
- `expiring_in_90d` `int` NOT NULL
- `active_subscriptions` `int` NOT NULL
- `source_run_id` `bigint` FK -> `source_runs(id)`
- `created_at` `timestamptz` NOT NULL
- `updated_at` `timestamptz` NOT NULL

## 索引

搜索相关：
- `companies.name` trigram GIN
- `products.name/reg_no/udi_di` trigram GIN
- `products` 组合全文索引（`name + reg_no + udi_di`）

Dashboard/查询相关：
- `products(company_id)`
- `products(status)`
- `products(approved_date)`
- `products(expiry_date)`
- `change_log(product_id, change_date desc)`
- `change_log(change_type, change_date desc)`
- `source_runs(status, started_at desc)`
- `subscriptions(is_active)`
- `subscriptions(subscription_type, target_value)`
- `daily_metrics(metric_date)`

## Migration
- 文件：`/Users/GY/Documents/New project 2/migrations/0003_pr1_schema_foundation.sql`
- 幂等设计：
  - `CREATE ... IF NOT EXISTS`
  - `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
  - `CREATE INDEX IF NOT EXISTS`

## Checklist 自动校验
- 校验脚本：`/Users/GY/Documents/New project 2/scripts/verify_pr1_schema.sql`
- 执行方式：
  - `psql \"$DATABASE_URL\" -f /Users/GY/Documents/New\\ project\\ 2/scripts/verify_pr1_schema.sql`
- 结果：
  - 全部通过时输出 `NOTICE: PR1 checklist passed ...`
  - 任一项失败时抛出 `RAISE EXCEPTION` 并非 0 退出

### CI 可读版本
- 校验脚本：`/Users/GY/Documents/New project 2/scripts/verify_pr1_schema_ci.sql`
- 执行方式：
  - `psql \"$DATABASE_URL\" -f /Users/GY/Documents/New\\ project\\ 2/scripts/verify_pr1_schema_ci.sql`
- 输出格式：
  - `CHECKLIST_1_TABLES_EXIST=PASS|FAIL detail=...`
  - `CHECKLIST_2_FOREIGN_KEYS=PASS|FAIL detail=...`
  - `CHECKLIST_3_FUZZY_INDEXES=PASS|FAIL detail=...`
  - `CHECKLIST_4_DAILY_METRICS_PK=PASS|FAIL detail=...`
  - `CHECKLIST_5_IDEMPOTENT_MIGRATION=PASS|FAIL detail=...`
- 退出码：
  - 任一 FAIL 则最终 `RAISE EXCEPTION`，CI 可据此失败
