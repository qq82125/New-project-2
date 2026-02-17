# UDI注册证关联增强源 配置说明

## 数据源名称（建议）

- `UDI注册证关联增强源（DI/GTIN/包装）`

该源不只是规格补充，还承担：

- `DI -> products` 关联补全
- `registry_no/reg_no -> products.registration_id` 锚点增强
- 包装/规格/厂家等信息补全

## 强约束（已在代码中校验）

`source_query` 结果必须包含以下列约束，否则同步失败：

1. 必须包含 `updated_at`
2. 必须包含 `udi_di` 或 `di`（二选一）
3. 必须包含 `reg_no` 或 `registry_no`（二选一）

实现位置：

- `api/app/services/supplement_sync.py::_ensure_supplement_query_columns`

## 推荐 source_query（可直接用）

推荐优先使用视图，后台更清爽：

```sql
SELECT *
FROM public.v_udi_registration_enhance
WHERE updated_at >= :cutoff
ORDER BY updated_at DESC
LIMIT :batch_size
```

视图定义在迁移：

- `migrations/0027_create_udi_registration_enhance_view.sql`

如果你暂时不想建视图，可继续使用内联 SQL：

```sql
SELECT
  pv.di AS udi_di,
  COALESCE(NULLIF(pv.registry_no, ''), NULLIF(p.reg_no, '')) AS reg_no,
  COALESCE(NULLIF(p.name, ''), pv.product_name) AS name,
  COALESCE(NULLIF(p.model, ''), pv.model_spec) AS model,
  COALESCE(NULLIF(p.specification, ''), pv.model_spec) AS specification,
  p.category AS category,
  p.status AS status,
  p.approved_date AS approved_date,
  p.expiry_date AS expiry_date,
  p.class AS class,
  p.raw_json AS raw_json,
  p.raw AS raw,
  GREATEST(
    COALESCE(p.updated_at, TIMESTAMPTZ '1970-01-01'),
    COALESCE(pv.updated_at, TIMESTAMPTZ '1970-01-01')
  ) AS updated_at
FROM public.product_variants pv
LEFT JOIN public.products p ON p.id = pv.product_id
WHERE (p.is_ivd IS TRUE OR pv.is_ivd IS TRUE)
  AND GREATEST(
    COALESCE(p.updated_at, TIMESTAMPTZ '1970-01-01'),
    COALESCE(pv.updated_at, TIMESTAMPTZ '1970-01-01')
  ) >= :cutoff
ORDER BY updated_at DESC
LIMIT :batch_size
```

## 同步匹配策略（当前实现）

每条补充行按以下顺序匹配本地产品：

1. `udi_di`（或 `di`）精确匹配 `products.udi_di`
2. 若 1 未命中，再用 `reg_no/registry_no` 归一化匹配 `products.reg_no`

## 可观测指标（已落 source_runs.source_notes）

- `matched_by_udi_di`
- `matched_by_reg_no`
- `updated_by_udi_di`
- `updated_by_reg_no`
- `missing_identifier`
- `missing_local`
- `source_query_used`
- `source_table`

查看示例：

```sql
SELECT id, source, status, message, source_notes
FROM source_runs
WHERE source = 'nmpa_supplement'
ORDER BY id DESC
LIMIT 20;
```

## Admin 只读接口

最近补充同步分项统计（默认 20 条）：

`GET /api/admin/source-supplement/runs?limit=20`

返回字段包含：

- `matched_by_udi_di`
- `matched_by_reg_no`
- `updated_by_udi_di`
- `updated_by_reg_no`
- `missing_identifier`
- `missing_local`
- `source_query_used`
- `source_table`
