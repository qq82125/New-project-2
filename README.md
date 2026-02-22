# DeepIVD

DeepIVD 是一个面向 IVD 监管与产品情报的本地化平台，围绕“证据链 + 主锚点 + 可执行工作台”构建：
- Dashboard：入口页（KPI / Signals / Track / Trend）
- Search：检索工作台（统一 URL filters）
- Detail：证据资产页（Overview / Changes / Evidence / Variants）
- Benchmarks：对标集合与对比
- Admin：数据治理与运维控制台

---

## 1. 核心设计原则

1. 主锚点不变：`registration_no_norm -> registrations.registration_no -> products.reg_no`
2. 证据可回指：结构化写入必须关联 `raw_document_id` 与 evidence 信息
3. 不清库不重建：默认只做增量、补缺（fill-empty / only-missing）
4. UDI 防污染：默认跳过 outliers，关键监管事实字段不被 UDI 覆盖
5. 前端可执行：入口模块必须可钻取到 `/search` 或 `/detail`

---

## 2. 目录结构

- 后端：`/Users/GY/Documents/New project 2/api`
- 前端：`/Users/GY/Documents/New project 2/web`
- 迁移：`/Users/GY/Documents/New project 2/migrations`
- 脚本：`/Users/GY/Documents/New project 2/scripts`
- 文档：`/Users/GY/Documents/New project 2/docs`

关键文档：
- `/Users/GY/Documents/New project 2/docs/RUNBOOK.md`
- `/Users/GY/Documents/New project 2/docs/UDI_PARAMS_RUNBOOK.md`
- `/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_GOVERNANCE.md`
- `/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_CORE_V1.yaml`
- `/Users/GY/Documents/New project 2/docs/PARAMETER_DICTIONARY_APPROVED_V1.yaml`

---

## 3. 技术栈

- API：FastAPI + SQLAlchemy + PostgreSQL
- Worker：Python CLI（同步、审计、回填、治理任务）
- Web：Next.js + Tailwind + shadcn/ui
- 部署：Docker Compose（`db/api/worker/web/db-backup`）

---

## 4. 快速启动

### 4.1 常规启动

```bash
docker compose up -d --build
```

访问地址：
- Web: [http://localhost:3000](http://localhost:3000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4.2 安全启动（推荐）

```bash
./scripts/db_preflight.sh
./scripts/safe_up.sh
```

说明：`safe_up.sh` 会先做快照，再启动服务，降低“误挂载/误覆盖”风险。

### 4.3 停止

```bash
docker compose down
```

---

## 5. 挂载与数据目录

当前 compose 将宿主目录挂载为容器内统一导入根：
- 宿主：`/Users/GY/Documents/IIVD/000001 小桔灯网/4 数据库/产品数据库`
- 容器：`/data/import`（只读）

兼容链接：
- `/data/udi` -> `/data/import/udi/UDID_FULL_RELEASE_20260205`

约定：离线导入、旧证、UDI 都走 `/data/import` 体系。

---

## 6. 数据主链路（SSOT）

```text
raw_source_records.payload.registration_no_norm
  -> registrations.registration_no (canonical)
    -> products.reg_no
      -> product_params / product_variants
```

约束：
- `registrations.registration_no` 只允许 canonical（norm）
- `products.reg_no` 必须等于 `registrations.registration_no`
- 原始证号仅保留在 raw/meta，不写 canonical 字段

---

## 7. 常用命令（高频）

### 7.1 同步与指标

```bash
docker compose exec worker python -m app.workers.cli sync --once
docker compose exec worker python -m app.workers.cli daily-metrics --date 2026-02-22
docker compose exec worker python -m app.workers.cli daily-digest --date 2026-02-22
```

### 7.2 UDI（run 级别）

```bash
# 1) 生成 source run
docker compose exec worker python -m app.workers.cli source:run --source_key UDI_DI --execute

# 2) promote
docker compose exec worker python -m app.workers.cli udi:promote --execute --source-run-id <RUN_ID> --limit 2000 --offset 0

# 3) 审计
docker compose exec worker python -m app.workers.cli udi:audit --dry-run --source-run-id <RUN_ID> --outlier-threshold 100

# 4) 仅 allowlist 参数回填（默认跳过 outliers）
docker compose exec worker python -m app.workers.cli udi:params --execute --only-allowlisted --source-run-id <RUN_ID> --batch-size 500
```

### 7.3 旧证离线导入

```bash
# 按你项目内实际命令执行（支持 recursive / only-new / dataset_version）
# 参考 docs 与当前 CLI help
```

---

## 8. 参数字典与 allowlist 治理

- Core 字典：`PARAMETER_DICTIONARY_CORE_V1.yaml`
- Approved 字典：`PARAMETER_DICTIONARY_APPROVED_V1.yaml`
- allowlist 只能引用 `Core ∪ Approved`

校验：
```bash
python scripts/validate_core_param_dictionary.py
```

更新 baseline（仅在版本发布时）：
```bash
python scripts/validate_core_param_dictionary.py --update-baseline all
```

`udi:params --only-allowlisted` 写入时会落 `param_key_version = allowlist_version`，便于审计与回滚。

---

## 9. 本轮已落地的 UDI 结构化扩维

针对 run=41，已将高价值候选字段拆解写入 params（通过 allowlist 灰度）：

- `storage_json` ->
  - `STORAGE_TEMP_MIN_C`
  - `STORAGE_TEMP_MAX_C`
  - `TRANSPORT_TEMP_MIN_C`
  - `TRANSPORT_TEMP_MAX_C`
  - `STORAGE_NOTE`
- `packing_json` -> `PACKAGE_LEVEL`, `PACKAGE_UNIT`, `PACKAGE_QTY`
- `mjfs` -> `STERILIZATION_METHOD`
- `brand` -> `BRAND_NAME`

执行口径：
- 仅 allowlisted
- only-missing（已有非空不覆盖）
- 默认 `include_outliers=false`
- 每条记录写 evidence：`source_run_id/raw_document_id/di_norm/registration_no_norm`

---

## 10. 数据库安全与备份

- `db-backup` 每日 03:30 WAL，按周全量
- 备份目录：`/Users/GY/Documents/New project 2/backups/postgres`

手工触发：
```bash
docker compose exec -T db-backup /scripts/backup_pg_wal_daily.sh
docker compose exec -T db-backup /scripts/backup_pg_weekly_full.sh
```

健康检查：
```bash
./scripts/db_health_check.sh
./scripts/db_restore_drill.sh
```

---

## 11. 测试

```bash
cd /Users/GY/Documents/New project 2/api
pytest -q
```

若需 PG 集成测试：
```bash
./scripts/run_it_pg_tests.sh
```

---

## 12. 常见问题

### Q1: `docker compose up -d --build` 失败，提示 Docker Hub 超时 / connection reset
A: 网络到 Docker Hub 不稳定，不是代码错误。重试或先手动 pull 基础镜像后再 build。

### Q2: 为什么 params 没写入？
A: 常见原因是：
- allowlist 未包含目标 key
- `--resume` 已到末尾
- only-missing 下该 key 已有非空值
- 被 outlier 默认跳过

### Q3: 前端看不到数据
A: 先检查：
- `products` 是否有 anchor 映射（`reg_no`）
- `is_hidden=false` 视图是否去重后为空
- Search API 查询条件是否带了过严 filter

---

## 13. Git 工作建议

- 大变更分 PR，单 PR 聚焦单目标
- 每次仅提交本 PR 相关文件，避免夹带 `docker-compose.yml/.env` 等无关改动
- 先本地验证（typecheck/test/关键命令），再 push

