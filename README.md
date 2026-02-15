# IVD产品雷达

本项目用于汇总 IVD（试剂/仪器/医疗软件）产品变更信息，提供：
- NMPA/UDI 同步与补充数据源接入
- 严格 IVD 口径入库（默认仅 `is_ivd=true` 才写入主产品表）
- 证据链（raw 证据 + sha256 + 来源 URL + run_id + parse_log）
- 变更日志（`change_log`）与日指标（`daily_metrics`）
- 前台 Dashboard/检索与后台运维管理
- 数据治理：dry-run/execute/rollback（先归档再删除，可按 batch 回滚）
- 说明书/招采附件参数抽取 v1（规则优先 + evidence_text/page）

## 结构概览

目录：
- 后端：`api/`（FastAPI + SQLAlchemy + Postgres）
- 前端：`web/`（Next.js）
- 迁移：`migrations/`（按文件排序执行的 SQL migrations runner）

关键文档：
- 架构现状：`docs/ARCH_NOTES.md`
- 运行手册：`docs/RUNBOOK.md`
- PR1（现状适配版）：`docs/PR1_DB_MODEL_ADAPTED.md`
- 字段名表（DB Schema Dictionary）：`docs/FIELD_DICTIONARY.md`

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

## 主要接口（摘录）

用户侧：
- `GET /api/dashboard/summary|trend|rankings|radar`：日指标（IVD 口径）
- `GET /api/search`：检索（强制 IVD 口径）
- `GET /api/products/{id}`：产品详情（非 IVD 返回 404）
- `GET /api/products/{id}/params`：参数摘要（Pro，evidence_text/page/source_url）

Admin：
- `GET /api/admin/products`：产品列表（支持 `is_ivd=true|false|all` + `ivd_category` + `ivd_version`）
- `GET /api/admin/rejected-products`：非 IVD 拒收审计
- `GET /api/admin/stats`：后台统计卡片（IVD 总数/分布/拒收数量）
- `POST /api/admin/params/extract|rollback`：参数抽取/回滚

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
- 管理端产品列表 `GET /api/admin/products` 支持 `is_ivd=true|false|all`；非 IVD 审计走 `GET /api/admin/rejected-products`

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

查看 IVD 库存快照（分类/来源分布）：
```bash
curl -s http://localhost:8000/api/dashboard/breakdown
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

NHSA（月度快照）入库（证据链 raw_documents + 结构化 nhsa_codes；支持回滚）：
```bash
# 本地 CSV 文件
docker compose exec api python -m app.workers.cli nhsa:ingest --execute --month 2026-01 --file /path/to/nhsa.csv

# 或者配置 URL（低频）
docker compose exec api python -m app.workers.cli nhsa:ingest --execute --month 2026-01 --url https://example.com/nhsa.csv

# 回滚（按 source_run_id 删除本次 run 写入的 nhsa_codes）
docker compose exec api python -m app.workers.cli nhsa:rollback --execute --source-run-id 123
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
