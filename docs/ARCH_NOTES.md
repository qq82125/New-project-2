# 架构现状（PR0 Baseline Notes）

说明：本仓库当前目录结构为 `api/`（后端，FastAPI+SQLAlchemy+Postgres）与 `web/`（前端，Next.js），并非 `backend/`/`frontend/`。下文按“模块职责不变”的口径，列出实际文件路径与入口。

## 1) products 主表结构（后端）
- ORM 模型：`/Users/GY/Documents/New project 2/api/app/models/entities.py`（`class Product`, `__tablename__='products'`）
- 关键字段（核心识别/查询/口径）：
  - 标识：`id`(UUID), `udi_di`(唯一), `reg_no`(可空)
  - 基础信息：`name`, `class`(字段名 `class_name` 映射), `status`, `approved_date`, `expiry_date`, `model`, `specification`, `category`
  - IVD 口径：`is_ivd`, `ivd_category`, `ivd_subtypes`, `ivd_reason`, `ivd_version`, `ivd_source`, `ivd_confidence`
  - 原始字段：`raw`, `raw_json`
- 与“来源/证据链”相关表：
  - 同步运行：`source_runs`（`/Users/GY/Documents/New project 2/api/app/models/entities.py`）
  - 原始证据：`raw_documents`（`storage_uri/sha256/source_url/run_id/parse_log`）
  - 非 IVD 审计：`products_rejected`（可带 `raw_document_id`）
  - 清理归档：`products_archive`（带 `cleanup_run_id/archive_batch_id`）
  - 变更归档：`change_log_archive`（带 `cleanup_run_id/archive_batch_id`）

## 2) NMPA/UDI 同步触发点（后端）
- Worker CLI 主入口：`/Users/GY/Documents/New project 2/api/app/workers/cli.py`
  - 常用：`python -m app.workers.cli sync` / `python -m app.workers.cli loop`
- 同步实现主函数：`sync_nmpa_ivd()`：`/Users/GY/Documents/New project 2/api/app/workers/sync.py`
- 管理后台触发同步 API：
  - `POST /api/admin/sync/run`：`/Users/GY/Documents/New project 2/api/app/main.py`
- 同步数据流（简述）：
  - 下载 UDI 包（或走主数据源） -> staging 解压/解析 -> `ingest_staging_records()` upsert `products`（严格 IVD） -> 写 `change_log` -> 更新 `daily_metrics`

## 3) daily_metrics 表与计算位置（后端）
- ORM 模型：`DailyMetric`：`/Users/GY/Documents/New project 2/api/app/models/entities.py`
- 计算函数：
  - `generate_daily_metrics()`：`/Users/GY/Documents/New project 2/api/app/services/metrics.py`
  - `regenerate_daily_metrics()`：`/Users/GY/Documents/New project 2/api/app/services/metrics.py`
- 口径：metrics 相关 SQL join `products` 且强制 `Product.is_ivd IS TRUE`。

## 4) 前台搜索 API 路由与 SQL 条件（后端）
- 路由：`GET /api/search`：`/Users/GY/Documents/New project 2/api/app/main.py`
- Repository：`search_products()`：`/Users/GY/Documents/New project 2/api/app/repositories/products.py`
- SQL 基础条件：`build_search_query(..., ivd_filter=True)` 默认 `WHERE products.is_ivd IS TRUE`，再叠加 `q/company/reg_no/status`。

## 5) 后台列表 API 路由与 SQL 条件（后端）
- 产品列表（管理员）：
  - `GET /api/admin/products`：`/Users/GY/Documents/New project 2/api/app/main.py`
  - 口径：仅允许 `is_ivd=true`（非 IVD 走 `GET /api/admin/rejected-products` 审计）
- rejected 审计（管理员）：
  - `GET /api/admin/rejected-products`：`/Users/GY/Documents/New project 2/api/app/main.py`
- 运行记录/数据源：
  - `GET /api/admin/source-runs` / `GET /api/admin/data-sources`：`/Users/GY/Documents/New project 2/api/app/main.py`

