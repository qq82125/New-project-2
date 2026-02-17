# Ingest Runner（统一入口）

## 目标
在不重写现有爬虫/专项 ingest 的前提下，提供统一入口：
- `python -m app.cli source:run --source_key <KEY> [--dry-run|--execute]`
- `python -m app.cli source:run-all [--dry-run|--execute]`

## 命令
1. 单源运行
```bash
python -m app.cli source:run --source_key NMPA_REG --dry-run
python -m app.cli source:run --source_key UDI_DI --execute
```

2. 全量运行（只跑 `source_configs.enabled=true`）
```bash
python -m app.cli source:run-all --dry-run
python -m app.cli source:run-all --execute
```

## 统一流程（Runner）
1. 读取 `source_definitions + source_configs`
- `source_key`
- `parser_key`
- `fetch_params / parse_params / upsert_policy`
- `enabled`

2. 按 `parser_key` 路由
- 当前通用 Runner 已支持：
  - `nmpa_reg_parser`
  - `udi_di_parser`
  - `nhsa_parser`（适配现有 NHSA ingest）
  - `procurement_gd_parser`（适配现有集采 ingest）
- 其它 parser_key 当前标记为 `skipped`（不阻断其它源）。

3. Fetch
- 读取 `fetch_params` 建立连接并抓取行数据（支持 legacy 兼容）。
- 参数优先级（单一口径）：
  - 顶层 `fetch_params.*` 优先
  - 缺失时回退 `fetch_params.legacy_data_source.config.*`
  - 仍缺失时使用系统默认值
- 关键控制参数：
  - `batch_size`（默认 `2000`，范围 `1..20000`）
  - `cutoff_window_hours`（默认 `72`，范围 `1..8760`）

4. Parse / Normalize
- 每条记录提取并归一 `registration_no`。
- 若缺失 `registration_no`：
  - 计入 `missing_registration_no_count`
  - 写 `products_rejected`（`error_code=MISSING_REGISTRATION_NO`）
  - 不中断整批运行。

5. Raw（幂等）
- `--execute` 时每条记录写 `raw_source_records`。
- 幂等键：`(source_run_id, payload_hash)`（`payload_hash=SHA256(canonical json)`）。

6. Upsert（先 registrations）
- 先执行 `registrations` 合同化 upsert（`upsert_registration_with_contract`）。
- `udi_di_parser` 额外 upsert `product_variants`（DI 维度）。
- `nhsa_parser` / `procurement_gd_parser` 通过现有专项服务执行（不重写业务逻辑），由 Runner 统一触发与汇总。

## parser_key 运行参数约定（fetch_params）
1. `nmpa_reg_parser` / `udi_di_parser`
- 使用 `fetch_params.legacy_data_source.config`（或 `fetch_params.connection`）读取 PostgreSQL 数据。
- 推荐写法（避免双层歧义）：
  - 顶层放控制参数：`batch_size`、`cutoff_window_hours`
  - 连接信息放 `legacy_data_source.config` 或 `connection`
- 示例：
```json
{
  "batch_size": 2000,
  "cutoff_window_hours": 6,
  "legacy_data_source": {
    "type": "postgres",
    "config": {
      "host": "db",
      "port": 5432,
      "database": "nmpa",
      "username": "nmpa",
      "password": "***",
      "source_table": "public.products",
      "source_query": "SELECT * FROM public.products WHERE updated_at >= :cutoff ORDER BY updated_at DESC LIMIT :batch_size"
    }
  }
}
```
- SQL 参数约定：
  - Runner 会统一注入 `:batch_size` 与 `:cutoff`
  - `source_query` 可直接使用这两个参数

2. `nhsa_parser`
- 必填：`month`（`YYYY-MM`）
- 二选一：`url` 或 `file`
- 可选：`timeout_seconds`

3. `procurement_gd_parser`
- 必填：`province`
- 必填：`file`

## source_runs 统计口径
每次运行都会写 `source_runs`，并在 `source_runs.source_notes` 内记录以下指标：
- `raw_written_count`
- `parsed_count`
- `missing_registration_no_count`
- `registrations_upserted_count`
- `variants_upserted_count`
- `conflicts_count`
- `skipped_count`

同时保留通用批次字段：
- `records_total` = `fetched_count`
- `records_success` = `parsed_count`
- `records_failed` = `missing_registration_no_count + error_count`
- `added_count` = `registrations_upserted_count`
- `updated_count` = `variants_upserted_count`

## dry-run / execute
- `--dry-run`：只做读取、解析、计数，不写 `raw_source_records` 与业务表。
- `--execute`：执行完整写入链路。

适配器说明：
- `nhsa_parser`、`procurement_gd_parser` 复用现有服务实现，`dry-run` 语义沿用现有服务。
- 这两类源在 `dry-run` 下可能仍会写入证据链（如 `raw_documents`/`source_runs`），但不会执行正式结构化落库写入。

## 注意
1. 本 Runner 统一入口优先面向“注册证锚点链路”。
2. 对 NHSA/PROCUREMENT 等专项源，现有专用命令仍可继续使用（例如 `nhsa:ingest`、`procurement:ingest`）。
3. 配置治理建议：
 - 新增源时始终先定 `source_key + parser_key + fetch_params`，再决定是否需要 legacy 兼容块。
 - 不要在顶层和 nested 里长期保留不同的 `batch_size`；系统会按“顶层优先”执行，但建议保持一致便于排障。
