# Canonical Key Contract (Engineering Contract)

> 目的：固定全平台“唯一锚点”与 ingest 门禁规则，避免任何来源绕过锚点写入导致口径分叉。

## 1) Canonical Key（唯一锚点）

- canonical key = `normalize_registration_no(registration_no)` 的结果（规范化后的注册证号）。
- 全局唯一锚点表：`registrations.registration_no`，必须保持 **UNIQUE**（全系统唯一口径）。

## 2) Ingest 结构化写入规则（强制门禁）

所有数据源的 ingest 必须遵循同一条链路（不得跳过）：

1. Parse：从 payload 尝试解析 `registration_no`（可能来自 `registration_no/reg_no/registry_no/...`）。
2. Normalize：`normalize_registration_no` 归一化为 canonical key。
3. Anchor Gate：在任何结构化写入之前执行门禁判定：

### 2.1 解析不到 registration_no（或 normalize 失败）

- **禁止**写入 `registrations` / `products` / `product_variants` 的结构化数据（不得污染主表）。
- 只能写证据链 `raw_documents`（并记录 parse_log/错误码）。
- 必须进入 pending 队列（当前实现为 `pending_records`；下一步可抽象为 `pending_documents`）：
  - `reason_code`：`NO_REG_NO` 或 `PARSE_ERROR`
  - `raw_document_id` 可追溯

### 2.2 能解析到 registration_no（门禁通过）

强制写入顺序（不得反过来）：

1. `registrations`：先 upsert `registrations(registration_no)`
2. `products`：再写 `products`（保持前台口径：默认只展示 `products.is_ivd = true`）
3. 衍生实体：最后写 `variants/params/doc_links/procurement_*` 等

## 3) UDI 规则（规格层，不是产品锚点）

- `DI` 是规格/包装层（`di` **UNIQUE**）。
- 必须通过 `registration_no` 绑定到 `registrations`（允许 **1 证 : N DI**）。
- **禁止**用 DI 作为“产品唯一口径”。
- 若 UDI 记录只有 DI 但缺 `registration_no`：只能进入 pending 队列与证据链，等待人工/规则补锚。

## 4) 冲突覆盖策略（字段级）

同一 `registration_no` 的同字段冲突覆盖遵循：

1. `evidence_grade`（A > B > C）
2. 同 grade：`source_priority`（更高优先级胜出；由 `source_configs.upsert_policy.priority` 决定）
3. 同优先级：`observed_at`（新覆盖旧）

要求：
- 任何字段被覆盖，必须写 `change_log`（before/after）。
- 必须可追溯 `raw_document_id(raw_documents.id)` 或 `raw_id(raw_source_records.id)`。

## 5) 错误码规范（contract-level，至少 6 个）

错误码定义位置：
- `/Users/GY/Documents/New project 2/api/app/common/errors.py`：`IngestErrorCode`

必须稳定出现于 worker 日志/`source_runs.source_notes.error_code_counts`/`raw_documents.parse_log.error_code`：

- `E_CANONICAL_KEY_MISSING`：缺 registration_no
- `E_CANONICAL_KEY_CONFLICT`：同一 payload 内出现冲突的 registration_no（例如 `reg_no` 与 `registry_no` 不一致）
- `E_UDI_DI_WITHOUT_REG`：UDI payload 有 DI 但缺 registration_no
- `E_STRUCT_WRITE_FORBIDDEN`：门禁未通过但尝试结构化写入（防旁路）
- `E_EVIDENCE_GRADE_INVALID`：证据等级不在允许集合（A/B/C）
- `E_SOURCE_PRIORITY_INVALID`：source_priority 不可解析或非法

> 兼容：仓库仍保留历史错误码（如 `E_NO_REG_NO/E_REG_NO_NORMALIZE_FAILED/...`），但 contract-level 以本节为准。

## 已落地的位置（便于查找）

- 门禁与统一入口：
  - `/Users/GY/Documents/New project 2/api/app/services/ingest_runner.py`
    - `enforce_registration_anchor(record, source_key) -> AnchorGateResult`
    - `_run_one_source(...)`（parse 后、任何结构化写入前）
- 归一化函数：
  - `/Users/GY/Documents/New project 2/api/app/services/normalize_keys.py`
    - `normalize_registration_no(text) -> text | None`

