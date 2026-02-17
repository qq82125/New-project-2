# Procurement Minimal Structured Ingest (V1)

## Scope

This module adds a NHSA-style ingest path for provincial procurement snapshots:

- Evidence chain: `raw_documents`
- Run tracking: `source_runs`
- Structured tables:
  - `procurement_projects`
  - `procurement_lots`
  - `procurement_results`
  - `procurement_registration_map`

It does not change existing NMPA snapshots/diffs SSOT.

## Schema

Migration: `migrations/0026_add_procurement_minimal.sql`

- `procurement_projects(id, province, title, publish_date, status, raw_document_id, source_run_id, created_at)`
- `procurement_lots(id, project_id, lot_name, catalog_item_raw, catalog_item_std, created_at)`
- `procurement_results(id, lot_id, win_company_id, win_company_text, bid_price, currency, publish_date, raw_document_id, created_at)`
- `procurement_registration_map(id, lot_id, registration_id, match_type, confidence, created_at)`

Rollback SQL:

- `scripts/rollback/0026_add_procurement_minimal_down.sql`

## CLI

### Ingest

```bash
python -m app.workers.cli procurement:ingest --execute --file data/procurement_xxx.csv --province "广东"
```

Dry-run:

```bash
python -m app.workers.cli procurement:ingest --dry-run --file data/procurement_xxx.csv --province "广东"
```

Behavior:

- Always writes one `raw_documents` record (source=`PROCUREMENT`, run_id=`source_run:{id}`)
- Always creates one `source_runs` record (source=`procurement`)
- `--execute` writes to procurement structured tables
- `--dry-run` parses + evaluates mapping samples, but does not insert structured rows

### Rollback

```bash
python -m app.workers.cli procurement:rollback --execute --source-run-id 12345
```

Dry-run:

```bash
python -m app.workers.cli procurement:rollback --dry-run --source-run-id 12345
```

Rollback deletes in leaf-to-root order by `source_run_id`:

1. `procurement_registration_map`
2. `procurement_results`
3. `procurement_lots`
4. `procurement_projects`

`raw_documents` is retained as evidence.

## Input File (CSV/JSON)

Supported columns are permissive. Common aliases:

- project: `project_title` / `title` / `项目` / `项目名称`
- lot: `lot_name` / `lot` / `包组` / `分包` / `标段`
- catalog raw: `catalog_item_raw` / `catalog_item` / `目录项原文` / `目录项`
- catalog standardized: `catalog_item_std` / `目录项标准化` / `目录项标准` / `目录项`
- winner company: `win_company_text` / `winning_company` / `中标企业` / `中选企业` / `企业名称`
- price: `bid_price` / `price` / `中标价` / `中选价`
- publish date: `publish_date` / `发布日期` / `公告日期`
- status: `status` / `状态`
- currency: `currency` / `币种` (default `CNY`)

## Rule Mapping (Explainable)

For each lot (`catalog_item_std`), candidates are evaluated against `registrations` via linked `products`:

1. Name similarity:
   - `catalog_item_std` vs `products.name` (pg_trgm `similarity`)
   - `catalog_item_std` vs `registrations.raw_json::text` (pg_trgm `similarity`)
2. Methodology consistency bonus:
   - infer lot methodologies from `methodology_nodes.synonyms`
   - if overlap with `registration_methodologies`, add bonus
3. Winner company consistency bonus:
   - if `win_company_id` equals a linked `products.company_id`, add bonus

Confidence is combined into `procurement_registration_map.confidence` (0~1), with `match_type='rule'`.

## Admin Manual Correction API

`POST /api/admin/procurement/lots/{lot_id}/map-registration`

Payload:

```json
{
  "registration_no": "国械注准2024xxxxxx",
  "confidence": 0.95
}
```

Behavior:

- Resolves `registration_no -> registrations.id`
- Upserts into `procurement_registration_map` with `match_type='manual'`
- Repeated calls are idempotent on `(lot_id, registration_id)`
