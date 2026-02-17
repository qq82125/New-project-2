# Source Registry Baseline

## Baseline file
- `/Users/GY/Documents/New project 2/docs/source_registry_baseline_20260217_010646.json`
- `/Users/GY/Documents/New project 2/docs/source_registry_baseline_20260217_010646.upsert.sql`

说明：
- 包含当前 `source_definitions` 与 `source_configs` 的生产基线快照。
- `fetch_params` 中数据库密码已脱敏为 `***`。

## Usage
1. 作为备份基线：用于环境间对比、审计和回滚参考。
2. 作为迁移模板：在目标环境按 `source_key` 执行 upsert（先 definitions，再 configs）。

## Execute upsert SQL
1. 编辑 SQL 中密码占位符：
- `__NMPA_DB_PASSWORD__`
- `__UDI_DB_PASSWORD__`

2. 执行：
```bash
docker compose exec -T db psql -U nmpa -d nmpa -f docs/source_registry_baseline_20260217_010646.upsert.sql
```

3. 校验：
```sql
SELECT source_key, enabled, schedule_cron
FROM source_configs
ORDER BY source_key;
```

## Restore order
1. `source_definitions`（按 `source_key` upsert）
2. `source_configs`（按 `source_key` upsert）

## Notes
- 若要直接恢复到新环境，请先把 `fetch_params.legacy_data_source.config.password` 补成目标环境凭据。
- 建议恢复后执行一次：
```bash
python -m app.cli source:run-all --dry-run
```
确认配置可用。
