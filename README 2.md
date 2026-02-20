# DeepIVD（Dashboard-First）

本项目用于汇总 IVD 产品变更信息，提供：
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

### 1) 一键启动（推荐）

```bash
docker compose up --build
```

### 2) 访问入口

- Web Dashboard: [http://localhost:3000](http://localhost:3000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Admin: [http://localhost:3000/admin](http://localhost:3000/admin)（仅 `admin` 角色可访问）

### 3) 停止

```bash
docker compose down
```

## 管理员初始化与登录

系统启动时会尝试用环境变量初始化管理员账号：

- `ADMIN_EMAIL` / `ADMIN_PASSWORD`（推荐，默认：`admin@example.com` / `admin12345`）
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`（兼容变量，含义同上）

流程：
1. `api` 服务启动时，如果该邮箱用户不存在则创建 `role=admin` 用户；如果已存在但不是 admin，会升级为 `admin`。
2. 打开 Web 登录页 [http://localhost:3000/login](http://localhost:3000/login) 使用上述账号密码登录。
3. 登录后左侧菜单会出现「管理后台」，进入 [http://localhost:3000/admin](http://localhost:3000/admin)。

说明：
- 普通用户可通过 [http://localhost:3000/register](http://localhost:3000/register) 注册，但无法访问 `/admin`。
- Web 管理后台使用的是登录态 + `role=admin`（并非 BasicAuth）。

## 会员体系（手动年度会员制）

### 1) 会员状态字段（users 快照）

系统使用 `users` 表保存“当前会员快照”：
- `plan`: `free` / `pro_annual`
- `plan_status`: `inactive` / `active` / `suspended`
- `plan_expires_at`: 到期时间（`TIMESTAMPTZ`，可为空）

历史开通/续费记录写入：
- `membership_grants`: 每次开通/续费写一条（`start_at/end_at/reason/note`）
- `membership_events`: 审计事件（`grant/extend/suspend/revoke`，payload 为 jsonb）

### 2) 权益口径（entitlements）

后端统一计算 `entitlements`（见 `/api/auth/me` 返回）：
- free 或 inactive 或 suspended 或已过期：
  - `can_export=false`
  - `max_subscriptions=3`
  - `trend_range_days=30`
- `pro_annual` 且 `active` 且未过期：
  - `can_export=true`
  - `max_subscriptions=50`
  - `trend_range_days=365`

### 3) admin 如何开通/续费/暂停/撤销

推荐使用 Web 管理后台：
1. admin 登录后进入 [http://localhost:3000/admin/users](http://localhost:3000/admin/users)
2. 搜索用户邮箱
3. 点击「开通 / 续费 / 暂停 / 撤销」
4. 操作成功后列表会自动刷新；详情页可查看 grants 历史

也可直接调用 API（仅 admin 可用）：
- `POST /api/admin/membership/grant`：开通（默认 12 个月）
- `POST /api/admin/membership/extend`：续费（在当前到期日基础上延长；过期则从当前时间开始）
- `POST /api/admin/membership/suspend`：暂停（不改到期日）
- `POST /api/admin/membership/revoke`：撤销（回到 free/inactive）

排错建议：
- 登录后访问 `/api/auth/me`：检查 `plan/plan_status/plan_expires_at` 与 `entitlements`
- `plan_status=suspended` 或 `plan_expires_at` 已过期时，权益会降级为 free

### 4) 本地一键验收流程（注册 → 开通 → 权益生效）

1. 启动：
```bash
docker compose up --build
```
2. 注册一个普通用户：
   - 打开 [http://localhost:3000/register](http://localhost:3000/register) 注册并登录
   - 访问 [http://localhost:8000/docs](http://localhost:8000/docs) 调用 `GET /api/auth/me`，确认 `plan=free` 且 `entitlements.can_export=false`
3. 用 admin 账号登录并开通年度会员：
   - 打开 [http://localhost:3000/login](http://localhost:3000/login) 用 `ADMIN_EMAIL/ADMIN_PASSWORD` 登录
   - 进入 [http://localhost:3000/admin/users](http://localhost:3000/admin/users) 搜索用户并点击「开通」
4. 切回普通用户验证权益：
   - 再次调用 `GET /api/auth/me`，确认 `plan=pro_annual`、`plan_status=active`，且 `entitlements` 生效（订阅上限/趋势范围/导出权限）

## 数据源配置（管理后台）

管理后台提供「数据源管理」：
- 配置会加密存储在 `data_sources.config_encrypted`
- API 不会返回密码字段（前端也不会回显）

必须配置（docker compose 默认已提供本地开发值）：
- `DATA_SOURCES_CRYPTO_KEY`

## 本地启动步骤（非 Docker）

1. 启动 Postgres（或使用 `docker compose up db`）
2. 后端迁移：
```bash
cd api
python -m app.db.migrate
```
3. 启动 API：
```bash
cd api
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
4. 启动 Web：
```bash
cd web
npm install
npm run dev
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

管理后台手动触发（Web）：
- 进入 `/admin`，在「同步控制」区点击「手动触发同步」（有确认弹窗）
- 对应 API：`POST /api/admin/sync/run`

可重跑说明：
- `daily_metrics` 按 `metric_date` upsert（同日重跑覆盖更新）
- 摘要推送按 `(digest_date, subscriber_key, channel)` 去重，默认同日不重复发送

## IVD 范围与规则版本

### IVD 范围定义
- `reagent`（试剂）
- `instrument`（仪器/设备）
- `software`（医疗软件）

同步与查询默认仅保留 `is_ivd=true` 数据进入主分析视图。

### 规则版本（当前 v1）
- `class_code` 以 `22` 开头：`is_ivd=true`, `ivd_category=reagent`
- `class_code` 以 `07` 开头，且名称命中 instrument 关键词并且不命中排除关键词：`instrument`
- `class_code` 以 `21` 开头，且名称命中 software 关键词：`software`
- 其他：`is_ivd=false`

## IVD 一键命令

### 1) 历史重打标（可重复执行）
```bash
# 安全预览（无副作用）
docker compose exec api python -m app.workers.cli reclassify_ivd --dry-run

# 真正执行
docker compose exec api python -m app.workers.cli reclassify_ivd --execute
```

### 2) 非 IVD 清理（先归档再删除）
```bash
# 安全预览（无副作用）
docker compose exec api python -m app.workers.cli cleanup_non_ivd --dry-run --recompute-days 365

# 真正执行（会归档到 products_archive 后删除主表非 IVD）
docker compose exec api python -m app.workers.cli cleanup_non_ivd --execute --recompute-days 365 --notes "manual cleanup"
```

## 清理与回滚步骤

### 执行清理
1. `reclassify_ivd --dry-run` 检查将更新数量  
2. `reclassify_ivd --execute` 写入最新规则标记  
3. `cleanup_non_ivd --dry-run` 查看将归档/删除数量  
4. `cleanup_non_ivd --execute` 执行归档删除并重算 `daily_metrics`

### 回滚（从归档恢复）
```bash
docker compose exec -T db psql -U "${POSTGRES_USER:-nmpa}" -d "${POSTGRES_DB:-nmpa}" < scripts/restore/restore_products_from_archive.sql
```
说明：可在 SQL 中增加 `cleanup_run_id` 条件恢复指定批次。

## 冒烟测试（注册→同步→统计→清理→验证）

```bash
# 安全模式（默认，仅 dry-run）
./scripts/smoke_ivd_pipeline.sh

# 执行模式（会执行重打标与清理）
./scripts/smoke_ivd_pipeline.sh execute
```

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

## 开发时常用命令

### 什么时候用 `docker compose up -d`

适用场景：
- 只是想把服务拉起来跑（不关心实时日志）
- 代码没改 Dockerfile/依赖，或者你确定镜像已经是最新的

常用命令：
```bash
docker compose up -d
```

想看日志：
```bash
docker compose logs -f api
docker compose logs -f web
docker compose logs -f worker
```

### 什么时候需要 `--build`

适用场景：
- 改了 `api/requirements.txt`、`web/package*.json` 等依赖文件
- 改了 `api/Dockerfile`、`web/Dockerfile`、`docker-compose.yml`
- 改了会影响构建产物的代码，并且你希望容器内立即生效（尤其是 `web` 生产构建）

常用命令：
```bash
docker compose up -d --build
```

### 如何只重启单个服务

只重启（不重建镜像）：
```bash
docker compose restart api
docker compose restart web
docker compose restart worker
docker compose restart db
```

只重建并重启某个服务：
```bash
docker compose up -d --build api
docker compose up -d --build web
docker compose up -d --build worker
```

## 可选 CI（基础）

项目包含基础 CI（后端测试 + 前端 build 检查）。
- 文件：`.github/workflows/ci.yml`
