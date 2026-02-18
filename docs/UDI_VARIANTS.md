# UDI Variants（udi:variants）契约与运行说明

目标：把 `udi_device_index` 中已解析且可绑定到 `registration_no` 的 UDI 规格（DI）写入到可消费的 `product_variants`（规格层），并在无法绑定时标记为 `unbound`，避免污染主表。

本契约为 `docs/UDI_FULL_CONTRACT.md` 的补充落地说明（见 3.3 Variants 落库字段引用）。

## 核心原则

- Canonical anchor：`registration_no_norm`（归一化后）必须能命中 `registrations.registration_no`，并拿到 `registrations.id` 才允许写 `product_variants`。
- DI 是规格层：`di_norm` 为唯一键（`product_variants.di UNIQUE`），一证可对应多 DI。
- 无法绑定注册证号：不得写 `product_variants`；只在索引表标记 `udi_device_index.status='unbound'`。

## 输入来源

- 表：`udi_device_index`
- 关键字段：
  - `di_norm`：DI 唯一键
  - `registration_no_norm`：归一后的注册证号（绑定锚点）
  - `model_spec`（ggxh）、`sku_code`（cphhhbh）
  - `manufacturer_cn`（ylqxzcrbarmc）
  - `packing_json`：packingList 解析结果（packings[] 数组，见 `docs/UDI_FULL_CONTRACT.md`）
  - `raw_document_id`：证据链追溯

## 写入目标（Upsert）

表：`product_variants`

写入字段（以 `di` 为唯一键 upsert）：
- `di` = `udi_device_index.di_norm`
- `registration_id` = `registrations.id`（通过 `registration_no_norm` 命中 `registrations.registration_no`）
- `registry_no` = `registration_no_norm`（兼容旧口径查询）
- `model_spec` = `ggxh + ' / ' + cphhhbh`（缺失字段则只保留存在的一项；两者都缺则为 NULL）
- `manufacturer` = `udi_device_index.manufacturer_cn`
- `packaging_json` = `udi_device_index.packing_json`（按 schema 原样写入，通常为 JSON array）
- `evidence_raw_document_id` = `udi_device_index.raw_document_id`

冲突策略（同 DI 重复写入）：
- 只做补齐/幂等更新：已有非空字段不会被 NULL 覆盖（使用 `coalesce(excluded, existing)` 语义）。

## 无法绑定处理（Unbound）

当 `registration_no_norm` 为空，或无法在 `registrations.registration_no` 中找到对应记录：
- 不写 `product_variants`
- 仅在 `--execute` 模式下将 `udi_device_index.status` 更新为 `'unbound'`

注：`--dry-run` 不会写入 `unbound` 标记。

## CLI 用法

Dry-run（推荐先跑）：
```bash
python -m app.workers.cli udi:variants --dry-run --source-run-id <source_run_id> --limit 500
```

Execute（落库 + 标记 unbound）：
```bash
python -m app.workers.cli udi:variants --execute --source-run-id <source_run_id> --limit 500
```

输出字段：
- `scanned`：扫描的 `udi_device_index` 行数
- `bound`：成功命中注册证锚点的行数
- `unbound`：无法绑定的行数
- `upserted`：写入/更新的 `product_variants` 数
- `marked_unbound`：被标记为 `udi_device_index.status='unbound'` 的行数（仅 execute）
- `failed`：写入失败数（不应大于 0）
- `errors[]`：失败明细（包含 di 与 error）

## 前端验收（注册证详情）

注册证详情页会展示该注册证号下的 DI 列表与 `packaging_json` 的包装层级：
- 路由：`/registrations/{registration_no}`
- API：`GET /api/registrations/{registration_no}`（返回 `variants[]`）

当 `variants` 为空，页面会提示先运行 `udi:variants`。
