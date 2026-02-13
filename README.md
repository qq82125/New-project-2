# IVD 产品雷达 (IVD Product Radar)

面向体外诊断（IVD）的产品数据平台：聚合多数据源（NMPA/UDI/NHSA/招采等），以“证据链可追溯”为原则进行入库、清理归档与指标重算，并在前台/后台统一只展示 IVD 产品。

An IVD-focused product data platform that ingests authoritative sources (NMPA/UDI/NHSA/procurement), keeps an auditable raw evidence chain, enforces strict IVD-only persistence, supports cleanup/rollback and metrics recomputation, and shows IVD-only results in both user and admin UIs.

---

## Key Features / 核心功能

- 多数据源同步：NMPA Registry / NMPA UDI / NHSA（可扩展招采等）
- 严格 IVD 入库口径：默认只入库 `is_ivd=true`；非 IVD 可进入拒收审计（可选）
- 证据链可追溯：raw 原始文件落地 + `sha256` + `source_url` + `run_id`；解析/抽取保留日志与证据文本
- 历史清理归档与回滚：先归档再删除，按 `archive_batch_id` 回滚
- 指标重算：IVD 口径 daily metrics（按 scope 重算）
- 说明书/附件参数结构化（v1）：规则优先抽取关键参数并展示证据
- CLI：支持 `dry-run / execute / rollback`

---

## Tech Stack / 技术栈

- Backend: Python, FastAPI, SQLAlchemy, Postgres
- Frontend: Node.js, Next.js (App Router)
- Infra: Docker Compose
- Testing: pytest

---

## Getting Started / 快速开始

### 1) Clone / 克隆项目

```bash
git clone https://github.com/qq82125/New-project-2.git
cd "New project 2"
```

### 2) Install Dependencies / 安装依赖

#### Option A: Docker (Recommended) / Docker（推荐）

```bash
docker compose up -d --build
```

#### Option B: Local Python + Node / 本机 Python + Node

Backend:

```bash
python -m venv venv
source venv/bin/activate
pip install -r api/requirements.txt
```

Frontend:

```bash
cd web
npm install
```

### 3) Run / 运行

Docker:
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Local:

Backend:

```bash
PYTHONPATH=api uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd web
npm run dev
```

### 4) Run Tests / 运行测试

```bash
PYTHONPATH=api python -m pytest -q
```

---

## Usage Example / 使用示例

### CLI / 命令行（示例）

```bash
# 运行一次 UDI 同步（示例日期）
python -m api.app.cli source:udi --date 2026-02-13 --mode execute

# 全量 IVD 分类回填（先 dry-run 再 execute）
python -m api.app.cli ivd:classify --version ivd_v1_20260213 --mode dry-run
python -m api.app.cli ivd:classify --version ivd_v1_20260213 --mode execute

# 清理非 IVD（先 dry-run 再 execute）
python -m api.app.cli ivd:cleanup --mode dry-run
python -m api.app.cli ivd:cleanup --mode execute

# 回滚（按 archive_batch_id）
python -m api.app.cli ivd:rollback --mode execute --archive-batch-id <batch_id>

# 指标重算（IVD scope）
python -m api.app.cli metrics:recompute --scope ivd --since 2026-01-01
```

### API / 接口（示例）

```bash
# IVD 搜索（后端会强制 is_ivd=true）
curl "http://localhost:8000/api/products?query=PCR"

# 产品参数（说明书/附件抽取结果）
curl "http://localhost:8000/api/products/<product_id>/params"
```

### UI / 页面（示例）

- Dashboard: http://localhost:3000
- Search: http://localhost:3000/search
- Admin: http://localhost:3000/admin

---

## Configuration / 配置

### Admin bootstrap / 管理员初始化

启动时可通过环境变量初始化管理员账号（若用户不存在则创建；存在则可升级 role）：

- `ADMIN_EMAIL` / `ADMIN_PASSWORD`（默认：`admin@example.com` / `admin12345`）

### Data sources / 数据源

管理后台的数据源配置会加密存储，需提供：

- `DATA_SOURCES_CRYPTO_KEY`

---

## Documentation / 文档

- Runbook: `docs/RUNBOOK.md`
- Project structure: `docs/PROJECT_STRUCTURE.md`
- Architecture notes: `api/docs/ARCH_NOTES.md`

---

## Contributing / 贡献指南

欢迎贡献：

- 提交 Issue：说明问题、复现步骤、期望行为
- 提交 PR：保持改动小而聚焦，补充必要测试与文档
- 新增数据源：遵守“低频增量 + 缓存 + 可追溯证据链”，不做对抗式绕过

---

## License

MIT License.

