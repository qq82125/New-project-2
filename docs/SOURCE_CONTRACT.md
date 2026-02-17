# Source Contract（数据源统一契约）

版本：`v1.1`  
适用范围：所有接入源（NMPA/UDI、NHSA、集采、本地补充、外部补充）

## 0) 与当前仓库表单参数/模型的冲突评估
结论：方向一致，但有 3 个必须先补的缺口。

1. `registration_no` 作为唯一锚点可行，但不能替换 `registrations.id` 作为物理 PK。  
现有外键广泛依赖 `registrations.id`，所以采用“双键模型”：
- 业务主键（Canonical Key）：`registration_no`
- 技术主键（Technical PK）：`registrations.id`

2. 契约要求的专用表当前不存在：
- `raw_source_records`
- `product_udi_map`
- `udi_di_master`
- `pending_udi_links`

3. 现有数据源表单主要是连接参数（`host/port/database/source_table/source_query`），缺少冲突决策参数：
- `source_priority`
- `default_evidence_grade`
- `allow_without_registration_no`

## 1) Canonical Key 契约
全系统唯一口径：`registration_no`。

强制规则：
- 所有来源字段（`reg_no/registry_no/registration_no/...`）统一映射到 `registrations.registration_no`
- 任何跨表判等前必须执行 `normalize_registration_no`
- 允许保留 `products.reg_no`、`product_variants.registry_no` 作为冗余字段，但最终锚定以 `registrations.registration_no` 为准

## 2) Entity 层级定义
### 2.1 Registration（注册证实体）
- Canonical Key：`registration_no`
- 技术主键：`registrations.id`
- 职责：证级状态、有效期、证据、快照、版本事件

### 2.2 Product（展示/搜索层）
- 主表：`products`
- 与注册证关系：`products.registration_id -> registrations.id`
- `products.reg_no` 为兼容/回填字段，不作为最终判等主键

### 2.3 Variant（规格/包装层）
- 主表：`product_variants`
- `di` 唯一
- 一对多挂接注册证：`registry_no -> normalize -> registrations.registration_no`

## 3) 每个数据源必须执行四阶段管道（不得跳过）
### A. Fetch
- 拉取原始 payload
- 写 `raw_source_records`（必须包含 `payload_hash/source_url/evidence_grade/observed_at`）

### B. Parse
- 解析结构化字段，至少要尝试解析 `registration_no`
- 未解析到 `registration_no` 不能丢弃，必须入待处理队列

### C. Normalize
- 必须执行 `normalize_registration_no`
- 必须执行 `normalize_company_name`
- 同时保存 raw 值与 normalized 值

### D. Upsert
- 固定顺序：先 `registrations`，后衍生实体（`products/variants/procurement/price/...`）
- 每个 upsert 结果必须能追溯到 `raw_source_records.id` 与 `source_runs.id`

## 4) UDI 特殊规则
### 4.1 可解析 registration_no
- 必须写 `product_udi_map`，形成 `registration_no -> di` 映射

### 4.2 不可解析 registration_no
- 先写 `udi_di_master`
- 同步写 `pending_udi_links` 待映射队列

最小字段建议：
- `product_udi_map`: `id, registration_no, di, source, confidence, raw_source_record_id, created_at, updated_at`
- `udi_di_master`: `id, di, payload_hash, source, first_seen_at, last_seen_at, raw_source_record_id`
- `pending_udi_links`: `id, di, reason, retry_count, next_retry_at, status, raw_source_record_id`

## 5) 冲突处理（同一 registration_no 同字段不同值）
决策顺序固定为：
1. `evidence_grade`（A > B > C > D）
2. `source_priority`（值越小优先级越高）
3. `observed_at`（更近优先）

追溯要求：
- 必须记录 `raw_source_record_id`
- 必须写决策前后值（`before_json/after_json`）
- 必须写入 `change_log`（`entity_type='registration'` 或对应实体）

## 6) 与现有代码的落实映射
### 6.1 当前已满足
- `registrations.registration_no` 唯一约束已存在
- `normalize_registration_no`、`normalize_company_name` 已实现
- `raw_documents + source_runs + change_log` 已形成基础证据链
- UDI 主流程已能回填 `products.registration_id`

### 6.2 必须新增/调整
- 新增 4 张表：`raw_source_records/product_udi_map/udi_di_master/pending_udi_links`
- 在数据源配置层补参数：`source_priority/default_evidence_grade/allow_without_registration_no`
- 增加统一 stage runner（Fetch/Parse/Normalize/Upsert）与 stage 失败统计
- UDI ingest 强制执行“可解析入 map，不可解析入 pending”

## 7) 表单参数规范（兼容现有 UI）
保留原连接参数语义不变（避免影响已配置源）：
- `host`
- `port`
- `database`
- `source_table`
- `source_query`

新增逻辑参数（放 `data_sources.config`）：
- `source_priority: int`
- `default_evidence_grade: enum[A,B,C,D]`
- `enforce_registration_anchor: bool = true`
- `allow_without_registration_no: bool = false`
- `pending_queue_name: str | null`

## 8) 验收标准（DoD）
1. 任意入库记录可追溯到 raw（hash/url/grade）  
2. 任意 source 都有完整四阶段执行日志  
3. 未解析 `registration_no` 记录零丢失（进入 pending 队列）  
4. UDI `registration_no -> di` 映射覆盖率可统计  
5. 冲突决策可回放（依据与前后值完整）
