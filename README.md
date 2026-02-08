# NMPA IVD 注册情报看板（Dashboard-First）

本项目用于汇总 NMPA IVD 产品变更信息，提供：
- 每日数据同步
- 可检索的产品/企业信息
- Dashboard 趋势与榜单
- 每日订阅摘要推送（Webhook / Email）

## 架构图（ASCII）

```text
                 +-----------------------------+
                 |  NMPA UDI Download Source   |
                 +-------------+---------------+
                               |
                               v
+-------------------+   +------+-------+   +-------------------+
|  worker (Python)  +---> staging dir  +---> ingest/upsert DB  |
|  sync + metrics   |   | downloads/... |   | products/change.. |
+---------+---------+   +------+-------+   +---------+---------+
          |                        |                   |
          | daily-metrics          |                   v
          v                        |          +-------------------+
+-------------------+              |          | PostgreSQL        |
| daily_metrics     +--------------+          | companies/...     |
+-------------------+                         +----+---------+----+
                                                    |         |
                                                    v         v
                                            +-------+--+   +--+-------+
                                            | FastAPI  |   | Next.js  |
                                            | /api/*   |   | Dashboard|
                                            +----------+   +----------+
```

## 启动步骤

### 1) 准备环境变量

```bash
cp .env.example .env
```

### 2) 一键启动

```bash
docker compose up --build
```

### 3) 访问入口

- Web Dashboard: [http://localhost:3000](http://localhost:3000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Admin: [http://localhost:3000/admin](http://localhost:3000/admin)（账号密码来自 `.env` 中 `ADMIN_USERNAME`/`ADMIN_PASSWORD`）

### 4) 停止

```bash
docker compose down
```

## 数据同步说明

系统包含 `worker` 服务，持续循环执行同步任务：
- 下载 NMPA 包（支持 checksum）
- 解压到 `staging`
- 解析并 upsert 到 `products`
- 写入 `change_log`
- 生成 `daily_metrics`
- 触发每日订阅摘要推送

手动触发（容器内）：

```bash
# 单次同步
docker compose exec worker python -m app.workers.cli sync --once

# 生成某日聚合
docker compose exec worker python -m app.workers.cli daily-metrics --date 2026-02-08

# 发送某日摘要
docker compose exec worker python -m app.workers.cli daily-digest --date 2026-02-08
```

可重跑说明：
- `daily_metrics` 按 `metric_date` upsert（同日重跑覆盖更新）
- 摘要推送按 `(digest_date, subscriber_key, channel)` 去重，默认同日不重复发送

## Dashboard 口径说明

Dashboard 读取后端 `/api/dashboard/*`，核心口径如下：

- `summary`
  - `total_new`: 指定时间窗内 `change_log.change_type = new`
  - `total_updated`: 指定时间窗内 `change_log.change_type = update`
  - `total_removed`: 指定时间窗内 `change_log.change_type in (cancel, expire)`
  - `latest_active_subscriptions`: 当前 `subscriptions.is_active = true` 数量

- `trend`
  - 按 `daily_metrics.metric_date` 返回日级序列
  - 使用字段：`new_products/updated_products/cancelled_products`

- `rankings`
  - 基于 `daily_metrics` 选取窗口内 Top N 日期（新增/移除）

- `radar`
  - 使用最近一日 `daily_metrics` 的雷达维度

## 服务健康排查

1. 查看容器状态
```bash
docker compose ps
```
2. 查看日志
```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web
```
3. 数据库连通性
```bash
docker compose exec db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## 可选 CI（基础）

项目包含基础 CI（后端测试 + 前端 build 检查）。
- 文件：`.github/workflows/ci.yml`
