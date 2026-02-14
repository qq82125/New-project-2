# PR1 (适配现状)：数据库迁移与数据模型

本项目当前后端目录为 `api/`，使用“按文件排序执行的 SQL migrations”（`/Users/GY/Documents/New project 2/api/app/db/migrate.py`），不是 Alembic。PR1 的策略是：**优先对齐现有实现，补齐缺口与测试，不做破坏性类型重构**。

## 目标对齐
- products：IVD 口径字段
- raw_documents：证据链（storage_uri+sha256+source_url+run_id+parse_log）
- product_variants：DI 粒度补充（包装/厂家等）
- product_params：结构化参数（带 evidence_text/page 与 raw_document_id）
- products_archive：清理归档可回滚（带 archive_batch_id）
- products_rejected：非 IVD 拒收审计（可带 raw_document_id）
- change_log_archive：清理时变更记录归档（回滚可恢复）

## 已存在（无需重建）
- `products` IVD 字段：`migrations/0011_pri1_ivd_model.sql` + `migrations/0015_pri6_evidence_params_ivd_fields.sql`
  - `is_ivd` 当前允许 `NULL`（历史未分类场景）；后续如要改 `NOT NULL`，需先回填历史数据并确认 ingest/reclassify 不再写 `NULL`。
  - `ivd_version` 当前为 `INTEGER`（规则版本号如需字符串建议新增 `ivd_rule_version`，不要改类型）。
  - 约束：`ck_products_ivd_category_required`（`is_ivd IS NOT TRUE OR ivd_category IS NOT NULL`）。
- `raw_documents/product_variants/product_params/products_rejected`：`migrations/0015_pri6_evidence_params_ivd_fields.sql`
- `products_archive`：`migrations/0013_pri4_products_archive.sql`（列式快照表）+ `migrations/0015...` 增加 `archive_batch_id`
- `change_log_archive`：`migrations/0016_pri7_change_log_archive.sql`

## PR1 实际需要做的事（建议）
1. 确保 migrations runner 覆盖所有 `migrations/*.sql`（当前已覆盖）。
2. 增加真实 Postgres 集成测试：
   - 验证 migrations 可执行并创建表
   - 验证核心约束：`raw_documents` unique、`product_variants.di` unique、`product_params.raw_document_id` FK
   - 验证 cleanup/rollback 对 `products_archive/change_log_archive/daily_metrics` 的一致性
3. 文档化当前 canonical 值：
   - `ivd_category` 当前使用 `reagent/instrument/software`（小写字符串）
   - `ivd_source` 当前使用 `RULE` 等字符串（用于追溯分类来源）

## 本次补充的集成测试入口
- 临时 Postgres：`docker-compose.it.yml`（端口 55432）
- 一键脚本：`scripts/run_it_pg_tests.sh`
- 测试用例：
  - `api/tests/test_cleanup_rollback_integration_pg.py`
  - `api/tests/test_pr1_tables_integration_pg.py`

