# Canonical Key Contract

## 1) Canonical Key

- Canonical key: `registration_no`（归一后值）。
- 唯一锚点表：`registrations.registration_no`（全局唯一）。

## 2) Ingest 结构化写入约束

所有数据源在结构化写入前必须经过 registration anchor 门禁：

- 无法解析 `registration_no`：
  - 不得写 `registrations/products` 的结构化字段；
  - 仅写证据链 `raw_documents`；
  - 写入 `pending_records`，`reason_code` 必须是：
    - `NO_REG_NO`（缺失）
    - `PARSE_ERROR`（解析/归一失败）
- 可以解析 `registration_no`：
  - 必须先 `normalize_registration_no`
  - 先 upsert `registrations`
  - 再写衍生实体（如 `product_variants/product_params/nmpa_snapshots/field_diffs/...`）

## 3) UDI 规则

- `DI` 是规格/包装层（`di` 唯一），不是产品唯一口径。
- 通过 `registry_no -> registrations.registration_no` 绑定。
- 允许 `registration_no : di = 1 : N`。

## 4) 冲突策略与追溯

- 覆盖策略：`evidence_grade + source_priority + observed_at`
- 所有覆盖必须写 `change_log`
- 必须可追溯 `raw_document_id(raw_documents.id)` 或 `raw_id`

## 错误码

统一错误码定义：`api/app/common/errors.py`

- `E_NO_REG_NO`
- `E_REG_NO_NORMALIZE_FAILED`
- `E_PARSE_FAILED`
- `E_CONFLICT_UNRESOLVED`

`ingest_runner` 会将错误码计数写入：

- `source_runs.source_notes.error_code_counts`
- `source_runs.message`（摘要）
- `raw_documents.parse_log.error_code`（行级）

## 已落实模块与关键函数签名

- `api/app/services/ingest_runner.py`
  - `enforce_registration_anchor(record: dict[str, Any], source_key: str) -> AnchorGateResult`
  - `run_source_by_key(db: Session, *, source_key: str, execute: bool) -> IngestRunnerStats`
  - `_run_one_source(...)`（门禁先于结构化 upsert）
- `api/app/common/errors.py`
  - `class IngestErrorCode(str, Enum)`
- `api/app/models/entities.py`
  - `class PendingRecord`

## 回滚

- 门禁相关表回滚：
  - `scripts/rollback/0033_add_pending_records_down.sql`
- 代码回滚：
  - 回退 `ingest_runner.py` 相关改动即可恢复旧行为。
