# Registration Anchor Enforcement

## 规则说明

在 `ingest_runner.py::run_source_by_key` 中，统一执行以下锚点规则：

1. `registration_no` 是唯一 canonical key。  
2. parse 后、任何结构化 upsert 前，先判断是否可解析 `registration_no`。  
3. 若不可解析：
   - 不写 `products/registrations/product_variants`；
   - 只写 `raw_documents`（证据链）；
   - 写 `pending_records`（待处理队列）；
   - 统计 `missing_registration_no_count++`。
4. 若可解析：
   - `normalize_registration_no`；
   - 先 upsert `registrations(registration_no)`；
   - 再写衍生结构化表（当前 runner 中主要是 `product_variants`）。
5. 所有 registration upsert 必须写 `change_log`（`entity_type='registration'`）。

## 触发条件

- 入口命令：
  - `python -m app.workers.cli source:run --source_key <KEY> --execute`
  - `python -m app.workers.cli source:run-all --execute`
- 生效代码：
  - `api/app/services/ingest_runner.py`

## 统计口径

`IngestRunnerStats` 新增并输出：

- `missing_registration_no_count`
- `registration_upserted_count`

兼容保留：

- `registrations_upserted_count`（旧字段，值与 `registration_upserted_count` 同步）

## 新增数据表

- `pending_records`
  - 用于承接“已抓取但缺 `registration_no`”的数据行
  - 关键字段：`source_key/source_run_id/raw_document_id/payload_hash/reason_code/status`

## 回滚说明

- 迁移：
  - `migrations/0033_add_pending_records.sql`
- 回滚：
  - `scripts/rollback/0033_add_pending_records_down.sql`

回滚只会删除 `pending_records` 表，不影响既有主业务表结构。
