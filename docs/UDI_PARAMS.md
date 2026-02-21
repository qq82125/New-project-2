# UDI Params V1 (Prompt6)

目标：在不“写爆”`product_params` 的前提下，把 UDI 的高价值参数（储运/灭菌/标签关键信息）以**可审计**的方式写入结构化表；同时产出一份“候选字段分布”统计，方便后续扩充白名单。

## 1) 两层机制

### A) 候选池统计（全量，不写主业务表）

表：`param_dictionary_candidates`

字段口径（每次执行写一份快照/更新）：
- `source='UDI'`
- `xml_tag`：来自 `udi_device_index` 的列名（例如 `mjfs`、`tscchcztj`、`storage_json`）
- `count_total / count_non_empty / empty_rate`
- `sample_values`：最多 10 个非空样例（字符串化）
- `source_run_id`：可选，用于对齐一次 ingest run

CLI（默认 dry-run，不落库）：
```bash
python -m app.workers.cli udi:params --dry-run --source-run-id <source_run_id> --top 50 --sample-rows 20000
```

Execute（仅写 `product_params`，默认不再先跑全量候选统计）：
```bash
python -m app.workers.cli udi:params --execute --only-allowlisted --source-run-id <source_run_id>
```

如需在 execute 同时落库候选池统计（耗时更高）：
```bash
python -m app.workers.cli udi:params --execute --with-candidates --source-run-id <source_run_id>
```

### B) 白名单写入 product_params（只写高价值）

配置：`admin_configs['udi_params_allowlist']`
审计键（同样在 `admin_configs`）：
- `udi_params_allowlist_version`（默认 `1`）
- `udi_params_allowlist_changed_by`
- `udi_params_allowlist_changed_at`
- `udi_params_allowlist_change_reason`

校验规则：
- allowlist 的每个 key 必须存在于 `docs/PARAMETER_DICTIONARY_CORE_V1.yaml` 或 `docs/PARAMETER_DICTIONARY_APPROVED_V1.yaml`
- `--dry-run --only-allowlisted`：提示非法 key 并计入 rejected
- `--execute --only-allowlisted`：若有非法 key 默认失败退出（可用 `--allow-unknown-keys` 临时放行）

默认 allowlist（幂等 seed 于迁移 `0044`）：
- `STORAGE`（来自 `udi_device_index.storage_json`，存 `storages[]` 数组）
- `STERILIZATION_METHOD`（`mjfs`）
- `SPECIAL_STORAGE_COND`（`tscchcztj`）
- `SPECIAL_STORAGE_NOTE`（`tsccsm`）
- `LABEL_SERIAL_NO`（`scbssfbhxlh`）
- `LABEL_PROD_DATE`（`scbssfbhscrq`）
- `LABEL_EXP_DATE`（`scbssfbhsxrq`）
- `LABEL_LOT`（`scbssfbhph`）

执行（只写 allowlisted 参数；要求能绑定到 `registration_no_norm -> registrations -> products(is_ivd=true)`，并且必须有 `raw_document_id` 作为证据）：
```bash
python -m app.workers.cli udi:params --execute --only-allowlisted --source-run-id <source_run_id> --limit 50000
```

版本写入：
- `product_params.param_key_version` 会写入当前 `udi_params_allowlist_version`

写入约束：
- 仅对 `udi_device_index.registration_no_norm` 非空的记录尝试写入。
- 仅对能定位到 `products (is_ivd=true)` 的注册证写入（避免污染非 IVD 展示口径）。
- `STORAGE`：
  - `product_params.param_code='STORAGE'`
  - `product_params.conditions={"storages":[...]}`
  - `product_params.value_text` 写入可读摘要（例如 `-18~55℃`），用于详情页直接展示
- 幂等去重：同 `registry_no + param_code + raw_document_id` 不重复写入。

## 2) 常见问题

### 为什么不直接把所有 UDI 字段都写入 product_params？

`udi_device_index` 字段多且长尾明显，直接落库会导致：
- 写入量爆炸（每个 DI / 每天增量都会重复写）
- 质量不可控（低价值字段噪声占比高）
- 前端展示难以稳定

因此 V1 只写 allowlist；候选池统计用于后续按数据分布扩充 allowlist。

## 3) 相关迁移

- `migrations/0044_add_udi_params_candidates.sql`
  - 新增 `param_dictionary_candidates`
  - 为 `udi_device_index` 增加 `scbssfbh*` 标签字段
  - seed `admin_configs['udi_params_allowlist']`
