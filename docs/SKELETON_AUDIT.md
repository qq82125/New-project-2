# 主键路径与骨架盘点（Registration-No Canonical）

范围：基于本仓库做“主键路径与骨架盘点”，不改任何业务逻辑；输出当前事实、入口与以 `registrations.registration_no` 为唯一主键的潜在一致性问题与 backfill 清单。

更新时间：2026-02-15

## 1) 技术栈与迁移规则确认

后端栈：
- FastAPI：`api/app/main.py`
- SQLAlchemy ORM：`api/app/models/entities.py` + `api/app/db/session.py`
- 数据库：Postgres（Docker 里 `postgres:16`）：`docker-compose.yml`

迁移 runner：
- 启动时自动执行：`docker-compose.yml` 中 `api` service 的 command：`python -m app.db.migrate && uvicorn ...`
- runner 实现：`api/app/db/migrate.py`

`migrations/*.sql` 执行规则（以 `api/app/db/migrate.py` 为准）：
- 迁移目录：repo 根目录下的 `migrations/`
- 顺序：按文件名排序（lexicographic）依次执行 `*.sql`
- 幂等：runner 不要求幂等，但本仓库迁移普遍使用 `IF NOT EXISTS`
- 去重：使用表 `schema_migrations(filename TEXT PRIMARY KEY, applied_at ...)` 记录已应用的 migration 文件名；重复启动不会重跑同名 migration
- 执行单元：每个 `.sql` 先通过 `split_sql_statements()` 进行语句切分（支持 `DO $$ ... $$`）后逐条执行（同一 migration 文件在一个事务块内执行）

## 2) “注册证唯一键”相关链路（当前骨架）

### canonical 唯一键
- `registrations.registration_no`：UNIQUE（canonical 注册证号）
  - ORM：`api/app/models/entities.py` 的 `class Registration`
  - DDL：`migrations/0001_init.sql`

### products 与注册证关系
- `products.reg_no`：nullable + index（非唯一）
- `products.registration_id`：nullable FK -> `registrations.id`
  - ORM：`api/app/models/entities.py` 的 `class Product`
  - 注意：当前 ingest/upsert 逻辑里并没有强制写入 `products.registration_id`（见第 3 节），所以该列即使存在，也可能长期为空。

### UDI DI 映射骨架（不新增表）
- `product_variants.di`：UNIQUE（canonical DI）
- `product_variants.registry_no`：nullable + index（DI -> 注册证号的“映射字段”，但未被强约束到 `registrations.registration_no`）
- `product_variants.product_id`：nullable FK -> `products.id`
  - ORM：`api/app/models/entities.py` 的 `class ProductVariant`
  - DDL：`migrations/0015_pri6_evidence_params_ivd_fields.sql`

## 3) registrations/products/product_variants 的写入（upsert）入口盘点

### products（主表）写入入口
- NMPA/UDI 同步主链：`api/app/workers/sync.py` -> `app.services.ingest.ingest_staging_records()`
  - 同步命令：`python -m app.workers.cli sync --once`（容器内常用：`docker compose exec worker ...`）
- 具体 upsert：`api/app/services/ingest.py::upsert_product_record()`
  - 匹配策略：`find_existing_product()` 使用 `(udi_di == record.udi_di) OR (reg_no == record.reg_no)`（存在“同 reg_no 多产品”与“reg_no 变更”导致误匹配风险，见第 5 节）
  - IVD 口径：`ingest_staging_records()` 会先用分类器判定 `is_ivd`；非 IVD 默认不写 `products`，写入 `products_rejected`（审计）

### product_variants（DI 粒度）写入入口
- NMPA/UDI 同步主链：`api/app/workers/sync.py` 在解析 UDI zip 后调用：`api/app/services/udi_variants.py::upsert_product_variants()`
  - 绑定逻辑：优先用 `Product.udi_di == di AND Product.is_ivd = true` 找产品并写入 `product_id`；否则 `product_id` 为空
  - `registry_no` 写入：来自 `app.sources.nmpa_udi.mapper.map_to_variant()` 的映射结果

### registrations（注册证 canonical）写入入口
- 目前写入入口来自“shadow-write NMPA 快照+diff”（见第 4 节）：`api/app/services/nmpa_assets.py::shadow_write_nmpa_snapshot_and_diffs()`
  - 逻辑：按 `Registration.registration_no == record.reg_no` 查找；不存在则创建；存在则更新 `filing_no/approval_date/expiry_date/status/raw_json`
  - 注意：这不是主产品入库口径的一部分（不改变 `products.is_ivd` 口径），但它会把 `registrations` 从“结构存在但可能空”变成“有数据资产”。

补充：本仓库还存在本地注册库补齐/增强任务，会调用 ingest 写入 products：
- `api/app/services/local_registry_supplement.py`（`python -m app.cli local_registry_supplement ...`）

## 4) NMPA snapshots/diffs（写入入口 + 触发命令）

### 写入入口（shadow-write）
- 写入函数：`api/app/services/nmpa_assets.py::shadow_write_nmpa_snapshot_and_diffs()`
- 触发点：`api/app/services/ingest.py::ingest_staging_records()`
  - 仅当 `source == 'NMPA_UDI'` 且该条记录被判定为 IVD 并成功 upsert `products` 后才会触发 shadow-write
  - 失败不阻断：shadow-write 异常会被吞掉并累计到 `stats['diff_failed']`
  - 失败记录：追加到 `raw_documents.parse_log.shadow_diff_errors`（best-effort）
  - 运行计数：`api/app/workers/sync.py` 会把 `diff_failed` 并入 `source_runs.records_failed`，并把 diffs 计数写入 `source_runs.source_notes`

### 运维/调试命令（只读，不写入）
- `python -m app.workers.cli nmpa:snapshots --since YYYY-MM-DD`
  - 实现：`api/app/workers/cli.py::_run_nmpa_snapshots()`（按 `snapshot_date` 聚合计数）
- `python -m app.workers.cli nmpa:diffs --date YYYY-MM-DD`
  - 实现：`api/app/workers/cli.py::_run_nmpa_diffs()`（按 `source_run_id/severity/field_name` 聚合）

## 5) 以 registration_no 为唯一主键的“一致性问题”清单（现状风险）

以下问题均是“骨架级”问题：不一定已发生，但从当前 schema/入口可推导出高概率风险点；建议用 SQL 体检或 IT 体检脚本验证。

### A. products ↔ registrations 的断链/弱链
- A1. `products.reg_no` 不为空但 `products.registration_id` 为空：当前 `upsert_product_record()` 不写 `registration_id`，因此此问题大概率大量存在。
- A2. `products.registration_id` 非空但与 `products.reg_no` 不一致：例如产品 reg_no 被更新但 registration_id 未同步。
- A3. `products.reg_no` 存在占位符/无效值：`api/app/services/data_quality.py` 已定义 `_PLACEHOLDER_REG_NO`，说明上游数据存在此类噪声。

建议体检 SQL（示意）：
- `products.reg_no` 有值但 `registration_id` 为空：
  - `SELECT count(*) FROM products WHERE reg_no IS NOT NULL AND btrim(reg_no)<>'' AND registration_id IS NULL;`
- `registration_id` 有值但 reg_no 为空：
  - `SELECT count(*) FROM products WHERE registration_id IS NOT NULL AND (reg_no IS NULL OR btrim(reg_no)='');`

### B. DI 映射无法回到 registration_no（product_variants 的弱约束）
- B1. `product_variants.registry_no` 有值但 `registrations` 中不存在同名 `registration_no`：因为 `registry_no` 不是 FK，也没有规范化约束。
- B2. `product_variants.product_id` 为空但实际上存在 `products.udi_di == product_variants.di` 的产品：当前 `upsert_product_variants()` 只在 `products.is_ivd = true` 时绑定；如果产品未被判为 IVD 或产品入库尚未发生，会导致长期空。
- B3. `product_variants.product_id` 指向的产品，其 `products.udi_di` 与 `product_variants.di` 不一致：理论上不应该发生，但如果历史数据被手工写入或后续补齐逻辑有 bug 会出现。

建议体检 SQL（示意）：
- registry_no 找不到 registrations：
  - `SELECT count(*) FROM product_variants pv LEFT JOIN registrations r ON r.registration_no=pv.registry_no WHERE pv.registry_no IS NOT NULL AND btrim(pv.registry_no)<>'' AND r.id IS NULL;`
- 有产品但未绑定 product_id：
  - `SELECT count(*) FROM product_variants pv JOIN products p ON p.udi_di=pv.di WHERE pv.product_id IS NULL;`

### C. products 的“按 reg_no 误匹配”风险
`find_existing_product()` 使用 `(udi_di==...) OR (reg_no==...)`：
- 同一注册证号可能对应多个 DI/规格（多条 products），此时按 reg_no 匹配会把“不同 DI 的产品”更新到同一行，造成串写。
- reg_no 发生变更/格式化变化时，也可能导致误匹配或重复新增。

这类风险一旦发生，会污染：`products` 快照、`change_log` 变更记录、以及后续 `nmpa_snapshots/field_diffs` 的“产品侧补充字段”。

### D. snapshots/diffs 覆盖范围天然受 IVD 口径限制
当前 shadow-write 触发点在 `ingest_staging_records()` 的 IVD 过滤之后：
- 对“非 IVD 记录”不会产生 `registrations/nmpa_snapshots/field_diffs`（这是设计取舍，但要在预期里）
- 若希望监管事实完整覆盖（不仅 IVD），需要未来单独一条“registrations-only”事实链路（本盘点不改逻辑，只提示风险）。

## 6) 建议 backfill 项列表（只列需要做的事情与风险点）

### Backfill-1：补齐 registrations（从 products.reg_no / product_variants.registry_no）
目标：确保 `registrations.registration_no` 作为 canonical 主键集合完整。
建议来源：
- `products.reg_no`（过滤 placeholder/空值）
- `product_variants.registry_no`（过滤空值）
风险点：
- reg_no 格式不一致（空格、全角/半角、括号等），可能造成“同一注册证被拆成多个 registration_no”。需要先定义规范化函数与冲突策略。

### Backfill-2：回填 products.registration_id（按 reg_no join registrations）
目标：让产品快照能稳定指向 canonical registration。
规则建议：
- `products.registration_id IS NULL AND products.reg_no` 可规范化后能匹配 `registrations.registration_no` 则回填
风险点：
- 同一 reg_no 对应多产品是允许的（不同 DI），回填应是多对一（多个 products 指向同一 registrations.id）。
- 若历史上 products.reg_no 被误写/占位符，回填会引入错误绑定；需要白名单/置信度/人工抽样。

### Backfill-3：回填/修正 product_variants.product_id（按 di join products.udi_di）
目标：稳固 `di -> product_id -> registration_id` 的路径。
风险点：
- 当前逻辑只绑定 IVD 产品；回填时是否也只绑定 IVD，需要明确（否则会把非 IVD 记录带入后续路径）。

### Backfill-4：补齐/规范化 product_variants.registry_no（以及与 registrations 的匹配）
目标：稳固 `di -> registry_no -> registrations` 的路径（不新增表的前提下）。
风险点：
- `registry_no` 并非强事实字段（可能来自解析/映射），需要保留 raw 证据链（目前主要靠 `raw_documents.parse_log` 与上游 zip）。

### Backfill-5（可选）：为历史 registrations 生成“初始快照”
目标：让 `nmpa_snapshots/field_diffs` 从某个基线开始可回放。
方案提示：
- 可用 `source_run_id = NULL` 或设定一个专用 run（更推荐）来写入基线快照
风险点：
- 没有上游 raw_document 时，证据链不足；需要定义“基线来源”并写入 `source_url/sha256/raw_document_id` 的空值策略。

---

完成：本文件仅做盘点与问题/回填清单，不修改任何业务逻辑。

