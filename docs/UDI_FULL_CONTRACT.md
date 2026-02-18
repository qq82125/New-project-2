# UDI 全量契约（V1）

目标：把 NMPA UDI 增量包（XML）稳定落到“可追溯原始证据 + 可消费结构化资产”，并与全平台 canonical key 规则一致。

本契约与 `docs/CANONICAL_KEY_CONTRACT.md` 一致：`registration_no_norm` 是唯一锚点；缺失则不得写入 `registrations/products/product_variants` 等结构化事实表。

## 1. Canonical Keys

### 1.1 DI（规格层唯一键）
- XML 字段：`<zxxsdycpbs>`
- 结构化字段：`di_norm`
- 归一规则（V1）：
  - `di_norm = trim(zxxsdycpbs)`
  - 若包含空白/分隔符，先去除空白；其余字符保持（UDI DI 通常为数字串或 GS1 编码）
- 约束：`udi_di_master.di` 全局唯一；`product_variants.di` 全局唯一。

### 1.2 注册证号（全平台唯一锚点）
- XML 字段：`<zczbhhzbapzbh>`
- 结构化字段：`registration_no_norm`
- 归一规则：使用 `normalize_registration_no()`。

### 1.3 是否有注册证
- XML 字段：`<sfyzcbayz>`
- 结构化字段：`has_cert`
- 规则：`has_cert = (sfyzcbayz == '是')`（兼容 `TRUE/true/1`）。

## 2. 结构字段（必须按 schema 落）

UDI XML 中的 `packingList` 与（可能存在的）`storageList` 必须被解析为结构化 JSON（用于下游消费与审计）。

### 2.1 包装层级 packingList -> packaging_json

XML 结构：
```xml
<packingList>
  <packing>
    <bzcpbs>...</bzcpbs>
    <cpbzjb>...</cpbzjb>
    <bznhxyjcpbssl>...</bznhxyjcpbssl>
    <bznhxyjbzcpbs>...</bznhxyjbzcpbs>
  </packing>
</packingList>
```

落库结构（JSONB）：`udi_di_master.packaging_json`
```json
{
  "packings": [
    {
      "package_di": "2697...",
      "package_level": "箱",
      "contains_qty": "10",
      "child_di": "0697..."
    }
  ]
}
```

字段映射：
- `packings[].package_di`  <= `<bzcpbs>`
- `packings[].package_level` <= `<cpbzjb>`
- `packings[].contains_qty` <= `<bznhxyjcpbssl>`
- `packings[].child_di` <= `<bznhxyjbzcpbs>`

约束：
- `package_di` 为空的 packing 必须丢弃（避免噪声）。
- 允许一个 `registration_no_norm` 对应多个 `di_norm`；不同规格（不同 DI）必须分别记录（不去重为单条产品）。

### 2.2 储运条件 storageList -> storage_json

优先解析 XML 结构（若存在）：
```xml
<storageList>
  <storage>
    <cchcztj>冷藏</cchcztj>
    <zdz>2</zdz>
    <zgz>8</zgz>
    <jldw>℃</jldw>
  </storage>
</storageList>
```

落库结构（JSONB）：`udi_di_master.storage_json`
```json
{
  "storages": [
    {
      "type": "冷藏",
      "min": "2",
      "max": "8",
      "unit": "℃",
      "range": "2-8℃"
    }
  ]
}
```

字段映射：
- `storages[].type` <= `<cchcztj>`
- `storages[].min` <= `<zdz>`
- `storages[].max` <= `<zgz>`
- `storages[].unit` <= `<jldw>`
- `storages[].range` = 拼接：`min + '-' + max + unit`（缺项时做降级：仅 min/max/unit 或原文）

兼容降级（当 `storageList` 不存在时）：
- 若存在 `<tscchcztj>`（文本型特殊储存条件）：写入
```json
{
  "storages": [
    {"type": "TEXT", "range": "<tscchcztj 原文>"}
  ]
}
```

## 3. 覆盖与写入规则（与 Anchor Gate 一致）

### 3.1 必须遵守 Anchor Gate
1) 若 **无法解析出** `registration_no_norm`：
- 允许写：`raw_documents/raw_source_records`（证据链） + `udi_di_master`（DI 全量资产） + `pending_udi_links`（待映射队列）
- 禁止写：`registrations/products/product_variants` 等依赖注册证锚点的结构化事实表

2) 若 **可解析出** `registration_no_norm`：
- 必须先：`normalize_registration_no()` -> `upsert registrations(registration_no)`
- 然后写：
  - `product_udi_map(registration_no, di, match_type='direct')`
  - `product_variants`（如有：包装/厂商等 DI 衍生字段）
  - `products`（仅当不存在时可创建 stub；或只补齐空字段）

### 3.2 UDI 的覆盖边界
- 允许“扩覆盖”（fill-empty / stub）：
  - `registrations/products` 可创建 stub（低证据，source_hint=UDI），仅用于锚点与可浏览性，不作为监管权威事实。
- 禁止覆盖 NMPA 权威字段（示例）：
  - 注册证：有效期、状态、变更结论（以 NMPA_REG / NMPA 注册库为准）
  - 产品：监管口径相关字段（如你已定义的 canonical 字段）
- 允许写入/补齐：
  - `product_variants`（DI/包装层级）
  - `product_params`（储运/灭菌/特殊条件，需带证据）

## 4. 可审计性要求

必须可追溯：
- `raw_document_id` / `raw_source_record_id`
- 覆盖/变更必须写 `change_log`（before/after）
- 冲突裁决：`evidence_grade + source_priority + observed_at`

## 5. 代码落点（实现约束）

- UDI XML 解析必须保留：
  - 扁平字段（例如 `zxxsdycpbs`/`zczbhhzbapzbh`/`sfyzcbayz`）
  - `packingList` 解析为 `packingList: list[dict]`
  - `storageList` 解析为 `storageList: list[dict]`（若存在）
- `write_udi_contract_record()` 必须：
  - 无 `registration_no_norm` 时不写 `registrations/products`
  - 写入 `udi_di_master.packaging_json` / `udi_di_master.storage_json`（按上面 schema）

