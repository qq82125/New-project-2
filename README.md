# DeepIVD

面向 IVD（试剂/仪器/医疗软件）的“监管事实驱动”产品雷达：从 NMPA/UDI 等来源同步数据，沉淀证据链与变更资产，提供检索/Dashboard/订阅投递，并逐步演进到“快照 + 字段级 diff + 风险与行动”的决策链路。

## 核心原则（不动摇）
- 严格 IVD 口径：前台默认只展示 `products.is_ivd = true`
- 证据链优先：Raw 不覆盖，结构化数据必须可回指证据（`raw_documents` / `product_params`）
- 资产化变更：基于 `change_log`（产品）+ `nmpa_snapshots/field_diffs`（注册证快照/diff）支撑订阅/日报/预警渐进接入

## 目录结构
- 后端：`api/`（FastAPI + SQLAlchemy + Postgres）
- 前端：`web/`（Next.js）
- 迁移：`migrations/`（按文件名排序执行的 SQL runner）
- 运维脚本：`scripts/`
- 文档：`docs/`

关键文档：
- 运行手册：`docs/RUNBOOK.md`
- 字段名表（DB Schema Dictionary）：`docs/FIELD_DICTIONARY.md`
- NMPA 快照+diff SSOT（人读）：`docs/NMPA_FIELD_DICTIONARY_V1_ADAPTED.md`
- NMPA 快照+diff SSOT（机器读）：`docs/nmpa_field_dictionary_v1_adapted.yaml`

## 前端信息架构（IA）
- `Dashboard`：入口页，只保留可钻取入口（KPI / Signals / Track / Trend），所有动作收敛到 `/search`。
- `Search`：工作台，统一 filters URL 契约与结果操作入口（含对标加入）。
- `Detail`：证据资产页（Overview / Changes / Evidence / Variants），返回链路保持筛选上下文。
- `Benchmarks`：对标集合与对比表（MVP 本地存储）。
- `Admin`：控制台能力集中在 `/admin/*`。
- `Pro`：转化入口，承接专业版权益说明与升级。

Signal Engine V1 API：
- 后端验收与运维：`docs/SIGNAL_ENGINE_V1_BACKEND.md`
- 覆盖迁移验证、signals-compute、Top/Batch API 验证与故障排查

## 主要数据资产（表级）
证据链：
- `raw_documents`：原始文档元数据（`storage_uri/sha256/source_url/run_id/parse_log`）
- `product_params`：参数抽取（必须包含 `raw_document_id + evidence_text (+evidence_page)`）

主业务：
- `products`：产品快照（前台 IVD-only 口径）
- `registrations`：注册证 canonical（`registration_no` UNIQUE）
- `product_variants`：UDI DI 粒度（`di` UNIQUE，包含 `registry_no` 映射）

变更与指标：
- `change_log`：产品变更日志（`changed_fields/before_json/after_json`）
- `daily_metrics`：日指标（IVD 口径）

NMPA 快照与字段级 diff（shadow-write，不改变前台口径）：
- `nmpa_snapshots`：注册证快照索引（`registration_id + source_run_id` 唯一）
- `field_diffs`：字段级 old/new（字段集合见 SSOT 的 `diff_fields`）
- 失败不阻断：diff 写入失败会追加到 `raw_documents.parse_log.shadow_diff_errors`，并计入 `source_runs.records_failed`

## 架构（简图）
```text
NMPA UDI / Primary Source
          |
          v
 worker(sync/metrics/digest) -> staging -> ingest/upsert -> PostgreSQL
                                              |
                                              v
                                         FastAPI / Next.js
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

## 数据保护与质量闸门
1. 固定 DB 数据目录（避免命名卷误新建）  
   `db` 已改为绑定仓库内目录：`/Users/GY/Documents/New project 2/.local/pgdata`
2. 固定调度备份（`db-backup` 服务）  
   每天 `03:30` 执行“日增量（WAL）”，每周（默认周一）`03:30` 追加“周全量（base backup）”  
   备份输出目录：`/Users/GY/Documents/New project 2/backups/postgres`
3. 注册证锚点闸门（防止再次出现大规模无产品映射）
   - 已接入 `sync_nmpa_ivd` 主流程：闸门失败会使本轮 sync 失败，并阻断后续 loop 作业。

手工执行锚点闸门：
```bash
MAX_RATIO=0.05 MAX_UNANCHORED_COUNT=500 ./scripts/check_registration_anchor_gate.sh
```

手工触发一次“日增量（WAL）”：
```bash
docker compose exec -T db-backup /scripts/backup_pg_wal_daily.sh
```

手工触发一次“周全量（base backup）”：
```bash
docker compose exec -T db-backup /scripts/backup_pg_weekly_full.sh
```

从备份恢复（示例）：
```bash
docker compose exec -T db psql -U nmpa -d nmpa -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
# 周全量 + WAL 归档恢复建议用 PostgreSQL PITR 标准流程（base backup + WAL replay）。
# base backup 目录默认在 backups/postgres/base/base_*
# WAL 归档目录默认在 backups/postgres/wal
```

可调环境变量：
- `BACKUP_RUN_AT`（默认 `03:30`）
- `FULL_BACKUP_WEEKDAY`（默认 `1`，周一）
- `FULL_BACKUP_RETENTION_WEEKS`（默认 `4`）
- `WAL_RETENTION_DAYS`（默认 `14`）
- `FULL_BACKUP_MAX_RATE`（默认 `80M`）
- 锚点闸门：`MAX_RATIO`（默认 `0.05`）、`MAX_UNANCHORED_COUNT`（默认 `0`，表示不启用绝对值闸门）
- Sync 内建闸门：`REGISTRATION_ANCHOR_GATE_ENABLED`（默认 `true`）、`REGISTRATION_ANCHOR_GATE_MAX_RATIO`（默认 `0.05`）、`REGISTRATION_ANCHOR_GATE_MAX_UNANCHORED_COUNT`（默认 `500`）

## 管理员初始化
系统启动时会尝试用环境变量初始化管理员账号：
- `ADMIN_EMAIL` / `ADMIN_PASSWORD`（默认：`admin@example.com` / `admin12345`）
- 兼容变量：`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`

## 迁移与回滚
迁移 runner：`python -m app.db.migrate`（内部使用 `schema_migrations` 记录已应用文件，避免重复执行）。

NMPA 快照/diff 迁移（幂等）：
- `migrations/0019_add_nmpa_snapshots.sql`
- `migrations/0020_add_field_diffs.sql`

回滚（手工执行，对现有 batch rollback 逻辑无影响）：
- `scripts/rollback/0019_add_nmpa_snapshots_down.sql`
- `scripts/rollback/0020_add_field_diffs_down.sql`
- `scripts/rollback/0034_add_daily_udi_metrics_down.sql`
- `scripts/rollback/0039_add_lri_query_indexes_down.sql`
- `scripts/rollback/0040_add_daily_lri_quality_metrics_down.sql`

## 常用命令（容器内）
一次同步：
```bash
docker compose exec worker python -m app.workers.cli sync --once
```

日指标 / 日报投递：
```bash
docker compose exec worker python -m app.workers.cli daily-metrics --date 2026-02-08
docker compose exec worker python -m app.workers.cli daily-digest --date 2026-02-08
```

查看 NMPA 快照/当天 diff（运维/调试）：
```bash
docker compose exec worker python -m app.workers.cli nmpa:snapshots --since 2026-02-01
docker compose exec worker python -m app.workers.cli nmpa:diffs --date 2026-02-08
```

说明书/文本参数抽取（dry-run/execute/rollback）：
```bash
docker compose exec api python -m app.workers.cli params:extract --dry-run --file /path/to/manual.pdf --di DI123
docker compose exec api python -m app.workers.cli params:extract --execute --file /path/to/manual.pdf --di DI123
docker compose exec api python -m app.workers.cli params:rollback --execute --raw-document-id <uuid>
```

NHSA（月度快照）入库（证据链 raw_documents + 结构化 nhsa_codes；支持回滚）：
```bash
docker compose exec api python -m app.workers.cli nhsa:ingest --execute --month 2026-01 --file /path/to/nhsa.csv
docker compose exec api python -m app.workers.cli nhsa:rollback --execute --source-run-id 123
```

非 IVD 清理/回滚（先归档再删除）：
```bash
docker compose exec api python -m app.workers.cli ivd:cleanup --dry-run
docker compose exec api python -m app.workers.cli ivd:cleanup --execute --archive-batch-id manual_batch_001
docker compose exec api python -m app.workers.cli ivd:rollback --execute --archive-batch-id manual_batch_001 --recompute-days 365
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
- `GET /api/admin/stats`：后台统计
- `POST /api/admin/params/extract|rollback`：参数抽取/回滚

## 测试
单测：
```bash
pytest -q
```

Postgres 集成测试（需要 `IT_DATABASE_URL`）：
```bash
./scripts/run_it_pg_tests.sh
```
