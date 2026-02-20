# DeepIVD 架构现状（PR0）

## 1) products 主表与核心字段
- 模型位置：`/Users/GY/Documents/New project 2/api/app/models/entities.py`
- 表：`products`
- 关键字段：
  - 标识：`id`, `udi_di`, `reg_no`
  - 产品基础：`name`, `class`, `status`, `approved_date`, `expiry_date`, `model`, `specification`, `category`
  - IVD 口径：`is_ivd`, `ivd_category`, `ivd_subtypes`, `ivd_reason`, `ivd_version`, `ivd_source`, `ivd_confidence`
  - 证据原始：`raw`, `raw_json`

## 2) NMPA/UDI 同步触发点
- Worker 主入口：
  - `python -m app.workers.cli sync`
  - 代码：`/Users/GY/Documents/New project 2/api/app/workers/cli.py`
- 具体同步实现：
  - `sync_nmpa_ivd()`：`/Users/GY/Documents/New project 2/api/app/workers/sync.py`
- 触发方式：
  - 手动 CLI（`sync` 子命令）
  - 常驻轮询：`python -m app.workers.cli loop`（`/Users/GY/Documents/New project 2/api/app/workers/loop.py`）
  - 管理后台可触发补充同步：`/api/admin/source-supplement/run`

## 3) daily_metrics 位置与计算逻辑
- 表模型：`DailyMetric`（`/Users/GY/Documents/New project 2/api/app/models/entities.py`）
- 计算函数：
  - `generate_daily_metrics()`：`/Users/GY/Documents/New project 2/api/app/services/metrics.py`
  - `regenerate_daily_metrics()`：`/Users/GY/Documents/New project 2/api/app/services/metrics.py`
- 口径：
  - SQL 已按 `Product.is_ivd IS TRUE` 过滤（新增/更新/过期风险）

## 4) 前台搜索 API 路由与 SQL 条件
- 路由：`GET /api/search`，实现文件：`/Users/GY/Documents/New project 2/api/app/main.py`
- Repository：`search_products()`，实现文件：`/Users/GY/Documents/New project 2/api/app/repositories/products.py`
- SQL 基础条件：
  - `where Product.is_ivd is true`
  - 其上叠加 query/company/reg_no/status 条件

## 5) 后台列表 API 路由与 SQL 条件
- 数据源列表：
  - 路由：`GET /api/admin/data-sources`
  - 实现：`/Users/GY/Documents/New project 2/api/app/main.py`
- 运行记录列表：
  - 路由：`GET /api/admin/source-runs`
  - 实现：`/Users/GY/Documents/New project 2/api/app/main.py`
- 产品类列表（管理员可扩展）：
  - 当前通用产品查询仍走 `/api/search` 与 `/api/products/full`，底层查询条件同样强制 `is_ivd=true`
