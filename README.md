# NMPA IVD 注册/备案产品查询工具

技术栈：FastAPI + Postgres + Next.js。
数据源优先：NMPA UDI 下载页每日包，并预留扩展到数据共享 API。

## PR 拆分实现

### PR1 数据库 schema 与迁移
- SQL 迁移：`migrations/0001_init.sql`
- 表：`products`、`companies`、`registrations`、`source_runs`、`change_log`
- 索引：全文检索 GIN（`to_tsvector`）+ trigram GIN（`gin_trgm_ops`）

### PR2 抓取器
- 文件：`api/app/services/crawler.py`
- 能力：解析每日更新包文件名/MD5/下载链接，下载、MD5 校验、解压到 staging
- `source_runs` 记录由 `app/repositories/source_runs.py` + `app/workers/sync.py` 维护

### PR3 解析与字段映射
- 文件：`api/app/services/mapping.py`
- 统一字段映射，保留 `raw_json`
- 增量 upsert + `change_log`：`api/app/services/ingest.py`

### PR4 后端 API
- 入口：`api/app/main.py`
- 路由：`/search`、`/product/{id}`、`/company/{id}`、`/status`

### PR5 前端
- Next.js 页面：
  - 搜索页：`web/app/page.tsx`
  - 产品详情：`web/app/product/[id]/page.tsx`
  - 企业详情：`web/app/company/[id]/page.tsx`
  - 更新状态：`web/app/status/page.tsx`

### PR6 部署
- Docker Compose：`docker-compose.yml`
- 服务：`api + db + web + worker`
- 定时：worker loop（`SYNC_INTERVAL_SECONDS`）
- 失败告警：日志 + 可选 `WEBHOOK_URL`

## 本地运行

1. 复制环境变量
```bash
cp .env.example .env
```

2. 启动
```bash
docker compose up --build
```

3. 访问
- Web: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000/docs](http://localhost:8000/docs)

## 测试

- 测试文件：`api/tests`
- 运行：
```bash
cd api
pip install -r requirements.txt
pytest -q
```
