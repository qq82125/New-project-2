# LRI V1 Repo Reality Check (Implementation Plan)

> 约束：本报告只基于当前仓库真实代码与目录结构做盘点，不改任何业务逻辑。

## 1) 数据库迁移 Runner：入口与用法（真实路径）

**Runner 模块路径**
- `/Users/GY/Documents/New project 2/api/app/db/migrate.py`

**调用方式（与 README 一致）**
- `python -m app.db.migrate`

**执行规则（来自实现代码）**
- 迁移目录：runner 通过 `Path(__file__).resolve().parents[3] / 'migrations'` 定位到仓库根目录下的 `migrations/*.sql`，按文件名排序执行。见 `/Users/GY/Documents/New project 2/api/app/db/migrate.py`。
- 幂等记录表：`schema_migrations`
  - 创建：`ensure_schema_migrations_table()` 会 `CREATE TABLE IF NOT EXISTS schema_migrations (...)`
  - 已应用迁移：`SELECT filename FROM schema_migrations`
  - 标记应用：`INSERT INTO schema_migrations(filename) ... ON CONFLICT DO NOTHING`
- SQL 拆分：runner 内置 `split_sql_statements()`，支持 Postgres 的 dollar-quote（如 `DO $$ ... $$`）避免误切分。

## 2) 核心表的 Model 定义位置（SQLAlchemy）

当前仓库的主要表 model 基本集中在：
- `/Users/GY/Documents/New project 2/api/app/models/entities.py`

按你关心的表逐一对应如下（均在 `entities.py`）：
- `registrations`：`class Registration(Base)`，`__tablename__ = 'registrations'`
- `products`：`class Product(Base)`，`__tablename__ = 'products'`
- `raw_documents`：`class RawDocument(Base)`，`__tablename__ = 'raw_documents'`
- `product_params`：`class ProductParam(Base)`，`__tablename__ = 'product_params'`
- `nmpa_snapshots`：`class NmpaSnapshot(Base)`，`__tablename__ = 'nmpa_snapshots'`
- `field_diffs`：`class FieldDiff(Base)`，`__tablename__ = 'field_diffs'`
- `change_log`：`class ChangeLog(Base)`，`__tablename__ = 'change_log'`
- `daily_metrics`：`class DailyMetrics(Base)`，`__tablename__ = 'daily_metrics'`
- `admin_configs`：`class AdminConfig(Base)`，`__tablename__ = 'admin_configs'`
- `source_runs`：`class SourceRun(Base)`，`__tablename__ = 'source_runs'`

补充：与 LRI 可能相关的既有实体（同文件）
- `registration_events`：`class RegistrationEvent(Base)`，`__tablename__ = 'registration_events'`（已存在，见 `migrations/0025_add_registration_events.sql`）
- `methodology_nodes` / `registration_methodologies`：已存在（见 `migrations/0023_add_methodology_nodes.sql`、`migrations/0024_add_registration_methodologies.sql`）
- `pending_records`：`class PendingRecord(Base)`，`__tablename__ = 'pending_records'`（已存在，见 `migrations/0031_add_pending_records.sql`）
- `pending_udi_links` / `udi_di_master` / `product_udi_map` / `raw_source_records`：已存在（用于 UDI/来源契约）
- `daily_udi_metrics`：`class DailyUdiMetrics(Base)`，`__tablename__ = 'daily_udi_metrics'`（已存在，见 `migrations/0034_add_daily_udi_metrics.sql`）

## 3) Worker/CLI 入口位置（用于后续加 derive-events 与 lri-compute）

仓库里 CLI/worker 的真实入口分两层：

**A) 统一 CLI 入口（runbook/容器命令实际走这里）**
- `/Users/GY/Documents/New project 2/api/app/workers/cli.py`
  - 使用 `argparse`，`build_parser()` 注册子命令
  - `main()` 解析 args 并按 `args.cmd` 分发到内部 `_run_*` 函数

**B) `python -m app.cli ...` 的薄封装**
- `/Users/GY/Documents/New project 2/api/app/cli.py`
  - 内容仅为 `from app.workers.cli import main`
  - 也就是说：`python -m app.cli <cmd>` 实际仍进入 `app.workers.cli:main`

**现有与 ingest/metrics 相关的关键子命令（用于后续扩展的落点）**
- `source:run` / `source:run-all`：统一 ingest runner 入口（见 `api/app/workers/cli.py` 中 `source_run`、`source_run_all`，以及 `_run_source_runner/_run_source_runner_all`）
- `daily-metrics`：日指标计算（`_run_daily_metrics`）
- `daily-digest`：订阅投递（`_run_daily_digest`）
- `nmpa:snapshots` / `nmpa:diffs`：快照/diff 运维查看
- `udi:audit`：UDI 绑定分布审计

因此：后续新增 `derive-events` / `lri-compute`，最贴近现有风格的落点就是：
- 在 `/Users/GY/Documents/New project 2/api/app/workers/cli.py` 新增子命令与 `_run_*` handler
- 如需对外兼容，也可在 `/Users/GY/Documents/New project 2/api/app/cli.py` 保持不变（它只是透传）

## 4) Web 前台/后台：LRI 最适合挂载的页面路由

### 前台（用户侧）推荐挂载 2 个路由（当前已存在）

1. 产品详情页（最贴合“单产品风险/行动建议”的展示位）
- `/products/[id]`
- 文件：`/Users/GY/Documents/New project 2/web/app/products/[id]/page.tsx`

2. 仪表盘首页（最适合做 LRI 概览卡、趋势、分布）
- `/`
- 文件：`/Users/GY/Documents/New project 2/web/app/page.tsx`

> 说明：当前 web 路由中未看到“注册证详情页（按 registration_no）”的独立页面；如 LRI 希望以 `registration_no` 为第一实体，后续可新增 `/registrations/[registration_no]` 作为 V2 产品化增强。

### Admin（后台）配置页推荐路由（当前已存在）

LRI 的“可运营配置”最贴近数据源/策略配置页：
- `/admin/sources`
  - 文件：`/Users/GY/Documents/New project 2/web/app/admin/sources/page.tsx`
-（可选）兼容旧数据源管理页：
  - `/admin/data-sources`
  - 文件：`/Users/GY/Documents/New project 2/web/app/admin/data-sources/page.tsx`

## 5) LRI V1 最小新增表：迁移文件名规划（从当前最大编号 +1）

### 当前迁移最大编号（仓库现状）
- 现有最大：`0034_add_daily_udi_metrics.sql`
- 因此下一号应从 **0035** 开始。

### 你提出的 LRI V1 “最小新增表”与仓库现状对齐结论

你列的最小表集合：
- `registration_events`
- `methodology_master`
- `product_methodology_map`
- `lri_scores`
- `pending_documents`

其中：
- `registration_events`：**已存在**（`migrations/0025_add_registration_events.sql` + `entities.py:RegistrationEvent`）。
- 方法学体系：仓库已有 **树 + 映射**（`methodology_nodes` + `registration_methodologies`）。这比单表 `methodology_master` 更强。
  - 因此建议：不要再引入新的 `methodology_master`，避免口径分叉；如确需“主方法学表”概念，可在文档层定义 `methodology_nodes` 为 master。
- `product_methodology_map`：当前已有 `registration_methodologies`（注册证维度）。若 LRI 需要“产品维度”，可以新增“产品到方法学”的派生映射表；但更推荐通过 `products.registration_id -> registrations -> registration_methodologies` 计算，不一定要落新表。
- `pending_documents`：当前已有 `pending_records`（结构化门禁失败队列）与 `raw_documents/raw_source_records`（证据链）。如果 “pending_documents” 只是“文档待解析队列”，可以复用 `pending_records` 并新增 reason_code/类型；不建议再起一套并行队列。

### 在“尽量不重复造轮子”的前提下，给出可执行的迁移规划（从 0035 开始）

**方案 A（推荐）：最小新增 1-2 张表，最大复用既有 registration_events/methodology_nodes/pending_records**
- `migrations/0035_add_lri_scores.sql`
  - 建议表：`lri_scores`（按 `registration_no` 或 `registration_id` + `score_date` 存每日/每次计算结果）
- `migrations/0036_add_pending_documents.sql`（仅当确认 `pending_records` 无法承载“文档级待解析”时才需要）

**方案 B（严格按你列的表名落库，但会与现有表重复，需要额外收敛策略）**
- `migrations/0035_add_methodology_master.sql`
- `migrations/0036_add_product_methodology_map.sql`
- `migrations/0037_add_lri_scores.sql`
- `migrations/0038_add_pending_documents.sql`
> 不建议：会与 `methodology_nodes/registration_methodologies/pending_records` 功能重叠，后续维护成本高。

**本报告建议采用方案 A**，并在 LRI 设计里把 “方法学 master = methodology_nodes，文档 pending = pending_records” 作为口径约束。

