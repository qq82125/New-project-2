# Company Resolution (Minimal Viable Alias System)

目标：在不改动现有业务口径的前提下，引入“企业别名体系（最小可用）”，让不同来源的企业原文（manufacturer/注册人名称等）能稳定解析到 canonical `companies.id`，并支持 admin 手工绑定别名后触发受影响产品回填。

## 1) 数据模型

新增表：`company_aliases`
- `id` uuid pk
- `alias_name` text（索引 + 唯一，建议存放 normalized key）
- `company_id` uuid fk -> `companies.id`（索引）
- `confidence` numeric(3,2)
- `source` text（rule/manual/import）
- `created_at`/`updated_at`

迁移：
- `migrations/0022_add_company_aliases.sql`

回滚：
- `scripts/rollback/0022_add_company_aliases_down.sql`

## 2) 归一化工具

函数：
- `normalize_company_name(name) -> text|None`
- 代码：`api/app/services/company_resolution.py`

归一化要点（V1）：
- 全半角归一（NFKC）
- 空白移除、括号统一（`（ ）` -> `( )`）
- 去除常见后缀（如 `有限公司/股份/集团/科技/医疗器械...`，仅在尾部迭代剥离）
- 仅保留：汉字 + 数字 + ASCII 字母（字母转大写）

可配置种子：
- `docs/company_alias_seed.json`
- 用于脚本 backfill 时加载（可人工维护）；运行时 API 不依赖该文件存在。

## 3) Backfill 脚本

脚本：
- `scripts/backfill_company_resolution.py`

支持：
- `--dry-run`：统计 products/company_raw 分布、可归一比例、冲突样例
- `--execute`：按规则解析企业并回填 `products.company_id`

执行策略（execute）：
1. 从 `products.raw_json/raw` 或已绑定 `company` 中提取“公司原文”
2. 计算 `normalized_name`
3. 优先命中 `company_aliases.alias_name == normalized_name`
4. 否则命中 `companies.name == normalized_name`
5. 都没有则创建 `companies(name=normalized_name)`
6. 写回 `products.company_id`

所有写入应记录 `change_log`（`entity_type/changed_fields/before_json/after_json`）。

## 4) Admin API（最小）

新增：
- `GET /api/admin/company-aliases?query=...`
- `POST /api/admin/company-aliases`（`alias_name -> company_id`）
  - 绑定成功后：触发受影响产品的 `company_id` 重新回填（best-effort）

## 5) 运维建议

- 首次落地建议流程：
  1) dry-run 看分布与冲突
  2) 先用 admin 手工绑定少量高频别名（`source=manual`）
  3) 再 execute 跑脚本回填
- 冲突（同 normalized_name 映射到多个 company）需人工介入：优先通过 `company_aliases` 明确绑定。

