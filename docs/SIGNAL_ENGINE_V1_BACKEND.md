# Signal Engine V1 Backend Runbook

本文用于本地/服务器端到端复现 Signal Engine V1（后端）：
- 迁移建表（`signal_scores`）
- 离线计算（`signals-compute`）
- API 验证（单体、Top、Batch）
- 常见故障排查

## 1) 数据库迁移与建表验证

### 1.1 启动服务
```bash
docker compose up -d --build
```

### 1.2 运行迁移（容器启动通常会自动执行；手动可再跑一次）
```bash
docker compose exec api python -m app.db.migrate
```

### 1.3 验证 `signal_scores` 表存在
```bash
docker compose exec -T db psql -U nmpa -d nmpa -c "\\dt signal_scores"
docker compose exec -T db psql -U nmpa -d nmpa -c "\\d+ signal_scores"
```

最小 SQL 验证：
```sql
SELECT count(*) FROM signal_scores;
```

## 2) 手动计算（离线预计算写库）

### 2.1 执行一次计算（12m 窗口）
```bash
docker compose exec worker python -m app.workers.cli signals-compute --window 12m --as-of 2026-02-19
```

可选参数：
```bash
docker compose exec worker python -m app.workers.cli signals-compute --help
```

### 2.2 幂等验证（同一天重复执行）
```bash
docker compose exec -T db psql -U nmpa -d nmpa -c "select count(*) from signal_scores where as_of_date='2026-02-19';"
docker compose exec worker python -m app.workers.cli signals-compute --window 12m --as-of 2026-02-19
docker compose exec -T db psql -U nmpa -d nmpa -c "select count(*) from signal_scores where as_of_date='2026-02-19';"
```

预期：同一 `as_of_date` 不翻倍（upsert 更新，不重复插入）。

## 3) API 验证（curl）

默认 API 地址：`http://localhost:8000`

### 3.1 单体信号（registration）
```bash
curl "http://localhost:8000/api/signals/registration/08110006156G22"
```

### 3.2 Top 榜单（首页）
```bash
curl "http://localhost:8000/api/signals/top-risk-registrations?limit=10"
```

### 3.3 Batch（Search/List badge）
```bash
curl "http://localhost:8000/api/signals/batch?registration_nos=08110006156G22,20142400045&as_of_date=2026-02-19"
```

## 4) 调度（worker loop）

`worker loop` 已接入 `signals_compute_daily`，按“每天 UTC 至少一次”触发：
- 当天已成功：跳过
- 当天未成功：执行 `signals-compute (window=12m, as_of=today)`
- 失败不阻断其他 loop 任务

日志关键词：
- `Job signals_compute_daily started`
- `Job signals_compute_daily finished`
- `Job signals_compute_daily skipped`

## 5) 常见问题排查

### 5.1 `/api/signals/*` 返回 404
- 检查 `app/main.py` 是否 `include_router(signals_router)`。
- 检查容器是否已重建：`docker compose up -d --build api worker`。

### 5.2 Top/Batch 返回 `items=[]`
- 常见原因：尚未执行 `signals-compute`。
- 先跑一次：
  `docker compose exec worker python -m app.workers.cli signals-compute --window 12m --as-of <today>`
- 另一个原因：上游锚点缺失（如 registration 无 track/company 映射），则 `track/company` 字段可能为空。

### 5.3 出现重复数据
- 检查唯一约束是否存在：
  `uq_signal_scores_entity_window_date (entity_type, entity_id, window, as_of_date)`。
- 检查写入是否使用 upsert（`ON CONFLICT ... DO UPDATE`）。
- 若历史坏数据已存在，先清理冲突数据再重跑 compute。
