# UDI Products Enrich（udi:products-enrich）契约与运行说明

目标：使用 `udi_device_index` 的字段补齐产品展示信息（products），提升详情页完整度，同时严格不覆盖 NMPA 权威事实字段。

## 核心原则

- 必须先绑定注册证锚点：`udi_device_index.registration_no_norm` 必须命中 `registrations.registration_no`。
- 仅补空（fill-empty）：仅当 `products` 对应字段为空或占位（如 `UDI-STUB`）时才写入列字段。
- 不覆盖 NMPA：若已有值（视为 NMPA/人工/更可信来源），不覆盖，只将 UDI 候选值写入 `products.raw_json` 的审计/别名区。
- 必须可追溯：每次实际写入 `products` 必须写 `change_log`，并在 `after_raw` 带上 `raw_document_id/source_run_id/di_norm`。

## 输入来源

表：`udi_device_index`

用到的字段：
- 名称候选：`product_name (cpmctymc)`、`brand (spmc)`
- 型号候选：`model_spec (ggxh)`
- 类别候选：`category_big (qxlb)`、`product_type (cplb)`、`class_code (flbm)`
- 描述：`description (cpms)`（会截断写入 snapshot）
- 锚点：`registration_no_norm`
- 证据：`raw_document_id`、`source_run_id`

## 绑定逻辑（强制）

1. 仅处理 `registration_no_norm` 非空的记录。
2. 通过 `registration_no_norm` 查到 `registrations.id`。
3. 以 `registrations.id` 作为锚点，选择展示产品：
   - `products.registration_id == registrations.id AND products.is_ivd == true`
   - 若同一注册证多个产品，取 `updated_at/created_at` 最新的一条作为展示对象。
4. 若未找到产品：跳过（不创建新产品）。

## 写入规则（仅补空）

当绑定到 `product` 后，允许写入以下列字段，但必须满足“目标字段为空/占位”：

- `products.name`：
  - 仅当当前为空或为占位值（例如 `UDI-STUB`）时写入
  - 候选顺序：`cpmctymc` -> `spmc`

- `products.model`：
  - 仅当为空时写入
  - 候选：`ggxh`

- `products.category`：
  - 仅当为空时写入
  - 候选顺序：`qxlb` -> `cplb`

说明：
- `flbm/cplb/qxlb` 不强行落入现有 products 结构字段（避免误映射），统一进入 `raw_json.search_fields.udi`。
- 描述 `cpms` 默认不写入列字段；仅写入 `raw_json.udi_snapshot.description`（截断），并且不覆盖 `raw_json.description`（若已存在）。

## raw_json 写入（可审计）

每条命中的记录都会写入/更新：
- `products.raw_json.udi_snapshot`：
  - `di_norm/registration_no_norm/product_name/brand/ggxh/qxlb/cplb/flbm/description/raw_document_id/source_run_id/observed_at`
- `products.raw_json.search_fields.udi`：
  - `{ qxlb, cplb, flbm }`（有值才写）
- `products.raw_json.aliases`：
  - `udi_names[]`：当 UDI 名称与当前 `products.name` 不一致时收集
  - `udi_models[]`：当 UDI 型号与当前 `products.model` 不一致时收集

## CLI 用法

Dry-run（推荐先跑）：
```bash
python -m app.workers.cli udi:products-enrich --dry-run --source-run-id <source_run_id> --limit 500
```

Execute（落库 + 写 change_log）：
```bash
python -m app.workers.cli udi:products-enrich --execute --source-run-id <source_run_id> --limit 500
```

可选参数：
- `--description-max-len`：UDI 描述写入 snapshot 的最大字符数（默认 2000）

输出字段（JSON）：
- `scanned`：扫描的索引行数
- `reg_bound`：命中 registrations 的数量
- `product_bound`：命中 products 的数量
- `updated`：实际写入更新的数量
- `skipped_no_product`：有注册证但无对应产品（跳过）
- `skipped_no_change`：无可补齐字段（跳过）
- `failed / errors[]`：失败与明细

## 验收口径

- 产品详情页显示更完整（`型号/类别/产品描述` 等能出现更多信息）。
- 既有 NMPA 字段不被覆盖：
  - 例如产品已存在 `name`/`raw_json.description` 时，`udi:products-enrich` 不会覆盖，只写入 `raw_json.udi_snapshot`/`aliases`。

