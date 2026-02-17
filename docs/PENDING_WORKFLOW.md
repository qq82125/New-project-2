# Pending Workflow

## 目标

当 ingest 记录无法解析 `registration_no` 时，不污染结构化主表，进入人工处理闭环。

## 数据表

`pending_records`

- `id` uuid pk
- `source_key` varchar(80)
- `raw_document_id` uuid fk -> `raw_documents.id`
- `reason_code` varchar(50)
- `candidate_registry_no` varchar(120) nullable
- `candidate_company` text nullable
- `candidate_product_name` text nullable
- `status` varchar(20) default `open`
- `created_at` timestamptz
- `updated_at` timestamptz

迁移：

- `migrations/0031_add_pending_records.sql`

## Ingest 行为

在 `api/app/services/ingest_runner.py` 中：

- parse 失败或无 `registration_no`：
  - 写 `raw_documents`
  - 写 `pending_records(status='open')`
  - 不写 `registrations/products/product_variants`

## Admin API

### 1) 列表

`GET /api/admin/pending`

参数：

- `status`：`open/resolved/ignored/pending/all`
- `limit`

### 2) 处理

`POST /api/admin/pending/{id}/resolve`

请求体：

```json
{
  "registration_no": "国械注准2026xxxx"
}
```

系统处理：

1. normalize + upsert `registrations`
2. 执行绑定（若 pending 原始 payload 含 `di`，则 upsert `product_variants.registry_no`）
3. 标记 `pending_records.status='resolved'`

## 可追溯

- 证据：`raw_documents`
- 注册证写入：`change_log(entity_type='registration')`
