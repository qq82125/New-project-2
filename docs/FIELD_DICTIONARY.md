# 字段名表（DB Schema Dictionary）

本文件描述“IVD产品雷达”仓库当前使用的 **Postgres 表与字段名**（以 `migrations/*.sql` 与 `api/app/models/entities.py` 为准）。

说明：
- `products` 主表严格口径：前台检索/详情等默认只读 `is_ivd = true`。
- 证据链：外部抓取/导入的原始内容写入 `raw_documents`，结构化参数写入 `product_params` 并关联 `raw_document_id`。
- 破坏性清理：先归档到 `products_archive` / `change_log_archive`，再删除；可按 `archive_batch_id` 回滚。

## 核心业务表

### `products`（主产品表，IVD-only 展示口径）
- `id` uuid PK
- `udi_di` varchar(128) UNIQUE, index
- `reg_no` varchar(120) index, nullable
- `name` varchar(500) index
- `class` varchar(120) nullable
- `approved_date` date nullable
- `expiry_date` date nullable
- `model` varchar(255) nullable
- `specification` varchar(255) nullable
- `category` varchar(120) nullable
- `status` varchar(20) index, default `ACTIVE`
- `is_ivd` boolean index, nullable
- `ivd_category` text nullable（试剂/仪器/软件，见业务枚举）
- `ivd_subtypes` text[] nullable
- `ivd_reason` jsonb nullable（规则命中与证据字段等）
- `ivd_version` int not null（分类规则版本）
- `ivd_source` varchar(20) nullable（RULE/ML/MANUAL/HYBRID 等）
- `ivd_confidence` numeric(3,2) nullable
- `company_id` uuid FK -> `companies.id`
- `registration_id` uuid FK -> `registrations.id`
- `raw_json` jsonb（结构化来源字段快照）
- `raw` jsonb（原始来源字段快照）
- `created_at` timestamptz
- `updated_at` timestamptz

### `companies`
- `id` uuid PK
- `name` varchar(255) UNIQUE, index
- `country` varchar(80) nullable
- `raw_json` jsonb
- `raw` jsonb
- `created_at` timestamptz
- `updated_at` timestamptz

### `registrations`
- `id` uuid PK
- `registration_no` varchar(120) UNIQUE, index
- `filing_no` varchar(120) nullable
- `approval_date` date nullable
- `expiry_date` date nullable
- `status` varchar(50) nullable
- `raw_json` jsonb
- `created_at` timestamptz
- `updated_at` timestamptz

### `product_variants`（UDI DI/规格粒度）
- `id` uuid PK
- `di` varchar(128) UNIQUE, index
- `registry_no` varchar(120) index, nullable
- `product_id` uuid FK -> `products.id`, nullable
- `product_name` text nullable
- `model_spec` text nullable
- `packaging` text nullable
- `manufacturer` text nullable
- `is_ivd` boolean not null, index
- `ivd_category` varchar(20) index, nullable
- `ivd_version` varchar(40) nullable
- `created_at` timestamptz
- `updated_at` timestamptz

## 证据链与参数抽取

### `raw_documents`（原始证据链）
- `id` uuid PK
- `source` varchar(40) index（NMPA_UDI/NHSA/MANUAL/...）
- `source_url` text nullable
- `doc_type` varchar(20) nullable（pdf/html/text/json/...）
- `storage_uri` text not null（本地路径或对象存储 URI）
- `sha256` varchar(64) not null
- `fetched_at` timestamptz not null
- `run_id` varchar(120) index（一次运行的标识）
- `parse_status` varchar(20) nullable（PENDING/PARSED/FAILED）
- `parse_log` jsonb nullable（解析/抽取日志）
- `error` text nullable

### `product_params`（结构化参数）
- `id` uuid PK
- `di` varchar(128) index, nullable
- `registry_no` varchar(120) index, nullable
- `param_code` varchar(80) index
- `value_num` numeric(18,6) nullable
- `value_text` text nullable
- `unit` varchar(50) nullable
- `range_low` numeric(18,6) nullable
- `range_high` numeric(18,6) nullable
- `conditions` jsonb nullable（提取条件/重复标记等）
- `evidence_text` text not null（证据文本片段）
- `evidence_page` int nullable（PDF 页码，1-based）
- `raw_document_id` uuid FK -> `raw_documents.id`, index
- `confidence` numeric(3,2) not null, default 0.5
- `extract_version` varchar(40) not null（抽取规则版本）
- `created_at` timestamptz

### `products_rejected`（非 IVD 拒收审计）
- `id` uuid PK
- `source` varchar(40)（非空约束与唯一键由迁移加强）
- `source_key` varchar(255) index（用于幂等 upsert）
- `raw_document_id` uuid FK -> `raw_documents.id`, nullable
- `reason` jsonb nullable（拒收原因/分类器输出）
- `ivd_version` varchar(40) nullable
- `rejected_at` timestamptz index

## 同步运行与变更历史

### `source_runs`（一次同步/导入运行）
- `id` bigserial PK
- `source` varchar(80) index
- `package_name` varchar(255) nullable
- `package_md5` varchar(64) nullable
- `download_url` text nullable
- `status` varchar(20) index（RUNNING/success/failed）
- `message` text nullable
- `records_total` int
- `records_success` int
- `records_failed` int
- `added_count` int
- `updated_count` int
- `removed_count` int
- `ivd_kept_count` int
- `non_ivd_skipped_count` int
- `source_notes` jsonb nullable
- `started_at` timestamptz
- `finished_at` timestamptz nullable

### `change_log`（产品变更日志）
- `id` bigserial PK
- `product_id` uuid FK -> `products.id`, nullable
- `entity_type` varchar(30) index
- `entity_id` uuid index
- `change_type` varchar(20) index（new/update/cancel/expire/noop）
- `changed_fields` jsonb
- `before_json` jsonb nullable
- `after_json` jsonb nullable
- `before_raw` jsonb nullable
- `after_raw` jsonb nullable
- `source_run_id` bigint FK -> `source_runs.id`, nullable
- `changed_at` timestamptz
- `change_date` timestamptz（用于日指标窗口统计）

### `daily_metrics`（日指标，IVD 口径）
- `metric_date` date PK
- `new_products` int
- `updated_products` int
- `cancelled_products` int
- `expiring_in_90d` int
- `active_subscriptions` int
- `source_run_id` bigint FK -> `source_runs.id`, nullable
- `created_at` timestamptz
- `updated_at` timestamptz

## 归档与回滚

### `products_archive`（产品归档快照）
- `archive_id` bigserial PK
- `id` uuid（原产品 id）
- `udi_di` varchar(128)
- `reg_no` varchar(120) nullable
- `name` varchar(500)
- `class` varchar(120) nullable
- `approved_date` date nullable
- `expiry_date` date nullable
- `model` varchar(255) nullable
- `specification` varchar(255) nullable
- `category` varchar(120) nullable
- `status` varchar(20)
- `is_ivd` boolean nullable
- `ivd_category` text nullable
- `ivd_subtypes` text[] nullable
- `ivd_reason` jsonb nullable
- `ivd_version` int
- `company_id` uuid nullable
- `registration_id` uuid nullable
- `raw_json` jsonb
- `raw` jsonb
- `created_at` timestamptz
- `updated_at` timestamptz
- `archived_at` timestamptz index
- `cleanup_run_id` bigint index, nullable
- `archive_batch_id` varchar(120) index, nullable（回滚定位键）
- `archive_reason` text nullable

### `change_log_archive`（变更日志归档）
- `archive_id` bigserial PK
- `id` bigint nullable（原 change_log.id）
- `product_id` uuid index, nullable
- `entity_type` varchar(30) index, nullable
- `entity_id` uuid index, nullable
- `change_type` varchar(20) index, nullable
- `changed_fields` jsonb nullable
- `before_json` jsonb nullable
- `after_json` jsonb nullable
- `before_raw` jsonb nullable
- `after_raw` jsonb nullable
- `source_run_id` bigint index, nullable
- `changed_at` timestamptz nullable
- `change_date` timestamptz nullable
- `archived_at` timestamptz index
- `cleanup_run_id` bigint index, nullable
- `archive_batch_id` varchar(120) index, nullable
- `archive_reason` text nullable

### `data_cleanup_runs`
- `id` bigserial PK
- `run_at` timestamptz index
- `dry_run` boolean
- `archived_count` int
- `deleted_count` int
- `notes` text nullable
- `created_at` timestamptz

## 订阅与导出

### `subscriptions`
- `id` bigserial PK
- `subscriber_key` varchar(120) index
- `channel` varchar(20) index（webhook/email）
- `email_to` varchar(255) nullable
- `subscription_type` varchar(30) index
- `target_value` varchar(255) index
- `webhook_url` text nullable
- `is_active` boolean index
- `last_digest_date` date nullable
- `created_at` timestamptz
- `updated_at` timestamptz

### `subscription_deliveries`
- `id` bigserial PK
- `subscription_id` bigint FK -> `subscriptions.id`, index
- `dedup_hash` varchar(64) index
- `payload` jsonb
- `status` varchar(20) index
- `sent_at` timestamptz nullable
- `created_at` timestamptz

### `daily_digest_runs`
- `id` bigserial PK
- `digest_date` date index
- `subscriber_key` varchar(120) index
- `channel` varchar(20)
- `status` varchar(20)
- `payload` jsonb
- `sent_at` timestamptz nullable
- `created_at` timestamptz

### `export_usage`
- `id` bigserial PK
- `usage_date` date index
- `plan` varchar(30) index
- `used_count` int
- `created_at` timestamptz
- `updated_at` timestamptz

## 管理后台配置与数据源

### `admin_configs`
- `id` bigserial PK
- `config_key` varchar(80) UNIQUE, index
- `config_value` jsonb
- `updated_at` timestamptz

### `data_sources`
- `id` bigserial PK
- `name` varchar(120) UNIQUE, index
- `type` varchar(20) index
- `config_encrypted` text（加密后的配置 JSON）
- `is_active` boolean index
- `created_at` timestamptz
- `updated_at` timestamptz

## 用户与会员

### `users`
- `id` bigserial PK
- `email` varchar(255) UNIQUE, index
- `password_hash` varchar(255)
- `role` varchar(20) index（admin/user）
- `plan` text index（free/pro_annual/...）
- `plan_status` text index（active/inactive/...）
- `plan_expires_at` timestamptz nullable
- `onboarded` boolean index
- `created_at` timestamptz
- `updated_at` timestamptz

### `membership_grants`
- `id` uuid PK
- `user_id` bigint FK -> `users.id`, index
- `granted_by_user_id` bigint FK -> `users.id`, index, nullable
- `plan` text index
- `start_at` timestamptz index
- `end_at` timestamptz index
- `reason` text nullable
- `note` text nullable
- `created_at` timestamptz

### `membership_events`
- `id` uuid PK
- `user_id` bigint FK -> `users.id`, index
- `actor_user_id` bigint FK -> `users.id`, index, nullable
- `event_type` text index
- `payload` jsonb
- `created_at` timestamptz

## 补充数据源

### `nhsa_codes`（NHSA 月度快照）
- `id` uuid PK
- `code` text index
- `snapshot_month` varchar(7) index（YYYY-MM）
- `name` text nullable
- `spec` text nullable
- `manufacturer` text nullable
- `raw` jsonb not null
- `raw_document_id` uuid FK -> `raw_documents.id`, index
- `source_run_id` bigint FK -> `source_runs.id`, index
- `created_at` timestamptz

