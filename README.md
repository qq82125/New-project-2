# IVD产品雷达

本项目用于汇总 IVD（试剂/仪器/医疗软件）产品变更信息，提供：
- NMPA/UDI 同步与补充数据源接入
- 严格 IVD 口径入库（默认仅 `is_ivd=true` 才写入主产品表）
- 证据链（raw 证据 + sha256 + 来源 URL + run_id + parse_log）
- 变更日志（`change_log`）与日指标（`daily_metrics`）
- 前台 Dashboard/检索与后台运维管理
- 数据治理：dry-run/execute/rollback（先归档再删除，可按 batch 回滚）

## 结构概览

目录：
- 后端：`api/`（FastAPI + SQLAlchemy + Postgres）
- 前端：`web/`（Next.js）
- 迁移：`migrations/`（按文件排序执行的 SQL migrations runner）

关键文档：
- 架构现状：`docs/ARCH_NOTES.md`
- 运行手册：`docs/RUNBOOK.md`
- PR1（现状适配版）：`docs/PR1_DB_MODEL_ADAPTED.md`

## 架构图（ASCII）

```text
                 +-----------------------------+
                 |  NMPA UDI / Primary Source  |
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
| daily_metrics     +--------------+          | products/...      |
+-------------------+                         +----+---------+----+
                                                    |         |
                                                    v         v
                                            +-------+--+   +--+-------+
                                            | FastAPI  |   | Next.js  |
                                            | /api/*   |   | Dashboard|
                                            +----------+   +----------+
```

## 快速启动（Docker）

```bash
docker compose up -d --build
```

访问：
- Web Dashboard: [http://localhost:3000](http://localhost:3000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Admin: [http://localhost:3000/admin](http://localhost:3000/admin)（仅 `admin`）

停止：
```bash
docker compose down
```

## 管理员初始化

系统启动时会尝试用环境变量初始化管理员账号：
- `ADMIN_EMAIL` / `ADMIN_PASSWORD`（默认：`admin@example.com` / `admin12345`）
- 兼容变量：`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`

普通用户可从 [http://localhost:3000/register](http://localhost:3000/register) 注册；`/admin` 仅 admin 角色可见。

## 数据口径与治理

IVD 范围：
- `reagent`（试剂）
- `instrument`（仪器/设备）
- `software`（医疗软件）

默认严格口径：
- 主产品查询/展示强制 `products.is_ivd IS TRUE`
- 非 IVD 数据不写主表，可写入 `products_rejected` 审计
- 管理端产品列表 `GET /api/admin/products` 仅支持 `is_ivd=true`；非 IVD 审计走 `GET /api/admin/rejected-products`

破坏性清理规则：
- 始终“先归档再删除”
- 归档批次 `archive_batch_id` 可用于回滚（同时覆盖 `products_archive` 与 `change_log_archive`）

证据链：
- `raw_documents`：`storage_uri + sha256 + source_url + run_id + parse_log`
- `product_params`：结构化参数必须带 `raw_document_id`，并保存 `evidence_text/page`

## 常用命令（容器内）

同步（一次）：
```bash
docker compose exec worker python -m app.workers.cli sync --once
```

生成某日指标 / 发送某日摘要：
```bash
docker compose exec worker python -m app.workers.cli daily-metrics --date 2026-02-08
docker compose exec worker python -m app.workers.cli daily-digest --date 2026-02-08
```

历史重分类（先 dry-run 再 execute）：
```bash
docker compose exec api python -m app.workers.cli ivd:classify --dry-run
docker compose exec api python -m app.workers.cli ivd:classify --execute
```

非 IVD 清理（先归档再删除）：
```bash
docker compose exec api python -m app.workers.cli ivd:cleanup --dry-run
docker compose exec api python -m app.workers.cli ivd:cleanup --execute --archive-batch-id manual_batch_001
```

回滚（按 batch 恢复 products + change_log，并重算指标）：
```bash
docker compose exec api python -m app.workers.cli ivd:rollback --execute --archive-batch-id manual_batch_001 --recompute-days 365
```

指标重算：
```bash
docker compose exec api python -m app.workers.cli metrics:recompute --scope ivd --since 2026-01-01
```

说明书/文本参数抽取（dry-run/execute/rollback）：
```bash
# 从本地文件上传为 raw_document 并抽取（dry-run）
docker compose exec api python -m app.workers.cli params:extract --dry-run --file /path/to/manual.pdf --di DI123

# 执行写入 product_params
docker compose exec api python -m app.workers.cli params:extract --execute --file /path/to/manual.pdf --di DI123

# 回滚（删除该 raw_document 对应的 product_params）
docker compose exec api python -m app.workers.cli params:rollback --execute --raw-document-id <uuid>
```

## 测试

单测：
```bash
pytest -q
```

临时 Postgres 集成测试（验证清理/回滚/指标与 PR1 表约束，一键启动临时库并自动清理）：
```bash
./scripts/run_it_pg_tests.sh
```
