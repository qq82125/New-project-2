# UDI 全量导入 (2026-02-05) Repo Reality Check + 执行计划 (Prompt0)

本文档用于在开始 20260205 UDI 全量导入前，基于**当前仓库真实实现**做一次 Reality Check，并固化执行前提、关键路径与编号规划。  
约束：本步骤只写文档，不改任何现有逻辑。

---

## 1) Docker Compose 服务与 Worker CLI 入口

### Compose 服务与启动方式

Compose 文件：
- `/Users/GY/Documents/New project 2/docker-compose.yml`

服务名（compose 内定义）：
- `db`：Postgres 16
- `api`：FastAPI，启动时先跑迁移，再启动 uvicorn
- `worker`：常驻轮询，入口 `python -m app.workers.cli loop`
- `web`：Next.js

当前关键启动命令（来自 compose）：
- `api`：`sh -c "python -m app.db.migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000"`
- `worker`：`sh -c "python -m app.workers.cli loop"`

Worker CLI 入口位置（argparse）：
- `/Users/GY/Documents/New project 2/api/app/workers/cli.py`（`build_parser()` + `main()`）

说明：
- `python -m app.workers.cli <subcommand>` 是统一的 worker/ops CLI 入口。
- 常驻 loop 的实现文件在：`/Users/GY/Documents/New project 2/api/app/workers/loop.py`（被 `cli.py` 调用）。

### 迁移 runner 入口（用于导入前 DB schema 检查）

迁移 runner 入口：
- `/Users/GY/Documents/New project 2/api/app/db/migrate.py`

执行方式（容器内常用）：
- `python -m app.db.migrate`

执行规则（真实实现要点）：
- 维护表 `schema_migrations(filename, applied_at)`，已应用迁移不会重复执行。
- 扫描 repo 根目录的 `migrations/*.sql`，按文件名排序依次执行未应用的迁移。
- 支持 `CREATE TABLE IF NOT EXISTS` 等幂等写法；SQL 被拆分为多条 statement 执行（支持 `DO $$ ... $$`）。

---

## 2) 本次导入涉及的核心表与模型位置（真实路径）

以下表在 ORM Model 中的定义位置：
- `registrations`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class Registration`）
- `products`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class Product`）
- `product_variants`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class ProductVariant`）
- `raw_documents`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class RawDocument`）
- `source_runs`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class SourceRun`）
- `daily_metrics`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class DailyMetric`）
- `admin_configs`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class AdminConfig`）

与 UDI 绑定/补充相关（ORM 中存在）：
- `product_udi_map`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class ProductUdiMap`）
- `product_params`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class ProductParam`）

重要说明（UDI index 表）：
- `udi_device_index` **目前没有 ORM Model 定义**（仓库中未找到 `__tablename__ = 'udi_device_index'`）。
- `udi_device_index` 的读写使用 SQL（`INSERT ... ON CONFLICT` / `SELECT ...`），实现位置：
  - `/Users/GY/Documents/New project 2/api/app/services/udi_index.py`
  - `/Users/GY/Documents/New project 2/api/app/services/udi_promote.py`
  - `/Users/GY/Documents/New project 2/api/app/services/udi_variants.py`
  - `/Users/GY/Documents/New project 2/api/app/services/udi_params.py`
  - `/Users/GY/Documents/New project 2/api/app/services/udi_products_enrich.py`

---

## 3) 已实现 / 待实现的 UDI 子命令清单（以当前仓库为准）

CLI 文件：
- `/Users/GY/Documents/New project 2/api/app/workers/cli.py`

### 已实现（可用）
- `udi:index`
  - 说明：从 extracted XML（`--staging-dir` 或 `staging/run_<source_run_id>/extracted`）解析 `<device>` 并写入 `udi_device_index`（不写 registrations/products/variants/params）。
  - 实现：`/Users/GY/Documents/New project 2/api/app/services/udi_index.py`
- `udi:promote`
  - 说明：从 `udi_device_index` 推进到 registration/product（会写 stub/绑定，遵循 contract 策略）。
  - 实现：`/Users/GY/Documents/New project 2/api/app/services/udi_promote.py`
- `udi:variants`
  - 说明：从 `udi_device_index` 推进到 `product_variants`（必须能绑定 registrations）。
  - 实现：`/Users/GY/Documents/New project 2/api/app/services/udi_variants.py`
- `udi:products-enrich`
  - 说明：基于 `udi_device_index` 做 products “只补空字段”增强（不覆盖 NMPA）。
  - 实现：`/Users/GY/Documents/New project 2/api/app/services/udi_products_enrich.py`
- `udi:params`
  - 说明：候选池统计 + allowlist 写入 product_params（从 `udi_device_index` 扫描，不回读 XML）。
  - 实现：`/Users/GY/Documents/New project 2/api/app/services/udi_params.py`
- `udi:audit`
  - 说明：DI 绑定分布审计（read-only）。

### 待实现（当前仓库不存在）
- `udi:raw-import`
  - 期望语义：把 UDI 发布包从 URL/本地解压/落 `raw_documents` 并写入 staging，再触发 `udi:index`。
  - 当前替代方案：本次 20260205 全量导入直接使用宿主机目录 bind-mount 到容器，传 `--staging-dir /data/udi` 跳过 raw-import。

---

## 4) 20260205 全量 XML 关键字段确认（写死，禁止漂移）

> 本段为“字段锚定”，后续所有解析/落库/验证都以此为准（尤其是 dry-run 的非空率与出现率）。

关键字段（单值）：
- DI：`<zxxsdycpbs>`（落库字段：`di_norm`）
- RegNo：`<zczbhhzbapzbh>`（落库字段：`registration_no_norm`，需 normalize）
- HasCert：`<sfyzcbayz>`，当值为 `是` => `has_cert = true`

packingList（结构）：
- `packingList/packing/bzcpbs` => `package_di`
- `packingList/packing/cpbzjb` => `package_level`
- `packingList/packing/bznhxyjcpbssl` => `contains_qty`
- `packingList/packing/bznhxyjbzcpbs` => `child_di`

storageList（结构）：
- `storageList/storage/cchcztj` => `type`
- `storageList/storage/zdz` => `min`
- `storageList/storage/zgz` => `max`
- `storageList/storage/jldw` => `unit`

解析函数（当前实现位置）：
- `/Users/GY/Documents/New project 2/api/app/services/udi_parse.py`
  - `parse_packing_list(device_xml) -> {"packings":[...], "source":"UDI", "parsed_at":...}`
  - `parse_storage_list(device_xml) -> {"storages":[...], "source":"UDI", "parsed_at":...}`

索引写入（当前实现位置）：
- `/Users/GY/Documents/New project 2/api/app/services/udi_index.py`
  - 读取 `<device>`，将 `packing_json` 与 `storage_json` 分别落成 JSON（当前落库时是 `jsonb`，内容为数组）。

---

## 5) 迁移文件编号规划（从当前最大编号 + 1 开始）

当前仓库 `migrations/` 最大编号：
- `0045_add_daily_metrics_udi_value_add.sql`（编号 = 45）

因此后续如需新增迁移，编号从 `0046_*.sql` 开始。

本次“20260205 全量导入标准化执行清单”若严格按现状执行（bind-mount + 现有 udi 子命令链路），**理论上不需要新增迁移**。  
但为了满足“全程禁止静默成功 / 状态可审计 / 批次可回滚”，建议预留以下迁移编号（是否落地由后续指令决定）：

- `0046_add_udi_device_index_import_audit_fields.sql`
  - 目的：为 `udi_device_index` 增加最小审计字段/索引（如 `import_batch`/`file_part_no`/`status` 索引增强），便于 part 1-20 分批验收与失败定位。
- `0047_add_source_runs_udi_exec_guard.sql`
  - 目的：将 “files_total=0 或 devices_parsed=0 => FAILED” 的 guard 结果可结构化写入 `source_runs.source_notes`，便于 Dashboard/运维统计一致。

备注：
- 上述仅为编号规划，不代表已经实现或必须实现；执行前以“现有代码是否已满足验收项”为准。

