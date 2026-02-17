# IVD产品雷达 — NMPA 字段字典（V1.0 适配版，SSOT）

目的：在不破坏现有 schema 的前提下，为 NMPA/UDI 数据打通“可审计快照 + 字段级 diff + 订阅投递”的资产化能力。
硬约束：
- 禁止 rename/delete 现有表与字段
- 禁止修改现有字段类型与语义
- 仅允许 ADD TABLE / ADD COLUMN（幂等，支持 rollback）
- 前台口径保持：默认只展示 products.is_ivd = true

## A. 仓库现状锚点（防混乱）
1) 主产品表：products（IVD-only 展示口径）  
2) 注册证 canonical：registrations.registration_no（UNIQUE）  
3) UDI DI canonical：product_variants.di（UNIQUE），并携带 registry_no  
4) 证据链 canonical：
   - raw_documents（sha256 + source_url + run_id + parse_log）
   - product_params（必须带 raw_document_id + evidence_text/page）
5) 同步批次 canonical：source_runs（added/updated/ivd_kept_count 等指标）

> 注：本字典只做“适配与补齐”，不改变你当前 IVD 分类字段（products.is_ivd / ivd_category / ivd_subtypes / ivd_reason / ivd_version / ivd_source / ivd_confidence）。

## B. V1 概念字段 → 现有字段映射（核心对照表）

| V1 概念字段 | 现有字段（canonical） | 现有字段（补充/冗余） | 处理策略 |
|---|---|---|---|
| product_id | products.id | - | 复用 |
| udi_di | products.udi_di | product_variants.di | 复用（products 口径） |
| nmpa_id（注册证号） | registrations.registration_no | products.reg_no / product_variants.registry_no | canonical 在 registrations；products.reg_no 保留 |
| product_name | products.name | product_variants.product_name | 复用 |
| class_type | products.class | - | 复用（不改字段名） |
| registration_date | registrations.approval_date | products.approved_date | canonical 在 registrations |
| expiration_date | registrations.expiry_date | products.expiry_date | canonical 在 registrations |
| status / lifecycle | products.status / registrations.status | - | 先保持现状；lifecycle_status 如需，建议 API 推导不落库 |
| company_name | companies.name | product_variants.manufacturer | canonical 在 companies |
| product_type（试剂/仪器/软件） | products.ivd_category | product_variants.ivd_category | 复用（你现有枚举） |
| methodology（方法学） | products.ivd_subtypes（text[]） | product_params(param_code=METHODOLOGY) | 不新增主表字段，优先复用 subtypes/params |
| storage_condition（存储条件） | product_params(param_code=STORAGE_CONDITION) | - | 必须带 raw_document_id 证据 |
| confidence_score | products.ivd_confidence | product_params.confidence | 复用（IVD分类置信度 vs 参数抽取置信度分开） |

## C. 需要新增的“资产化层”（只新增表，不碰旧表语义）

你当前已有 change_log，但缺少“面向注册证的快照索引 + 字段级 diff”。新增两张表即可：

### C1) nmpa_snapshots（新增）
用途：每次 NMPA 同步为注册证落一条快照（可回放、可审计）。
建议字段：
- id uuid PK
- registration_id uuid FK -> registrations.id   (canonical)
- raw_document_id uuid FK -> raw_documents.id
- source_run_id bigint FK -> source_runs.id
- snapshot_date date NOT NULL
- source_url text NULL
- sha256 varchar(64) NULL
索引：registration_id, snapshot_date, source_run_id
建议唯一：UNIQUE(registration_id, source_run_id)

### C2) field_diffs（新增）
用途：字段级变更（old/new），为订阅/预警/趋势提供结构化底座。
建议字段：
- id uuid PK
- snapshot_id uuid FK -> nmpa_snapshots.id
- registration_id uuid FK -> registrations.id
- field_name text NOT NULL         # 必须属于“可diff字段集合”
- old_value text NULL
- new_value text NULL
- change_type varchar(20) NOT NULL # REGISTER/RENEW/MODIFY/CANCEL/UNKNOWN
- severity varchar(10) NOT NULL    # LOW/MED/HIGH
- confidence numeric(3,2) NOT NULL DEFAULT 0.80
- source_run_id bigint FK -> source_runs.id
索引：registration_id, field_name, source_run_id

## D. 可 diff 字段集合（严格限制，避免噪声）
建议先支持这些字段名（与现有字段映射一致）：
- registration_no
- filing_no
- approval_date
- expiry_date
- status
- product_name
- class
- model / specification
- intended_use（如果你能从 NMPA 抓到并落在 raw_json 或 params）

severity 规则建议：
- HIGH：registration_no / status / expiry_date / intended_use
- MED：product_name / class / model/spec
- LOW：纯格式化/冗余字段

## E. 参数码（product_params.param_code）标准化建议
- STORAGE_CONDITION
- METHODOLOGY
- TARGET_DEPARTMENT
- IS_IMPORTED
- TARGET_CUSTOMER
要求：所有参数必须带 raw_document_id + evidence_text/page，符合你现有证据链规范。

## F. 禁止事项（确保不弄乱现有系统）
- 不新增 udi_nmpa_map 表（你已有 product_variants 承担 DI↔注册证映射）
- 不重命名 products.reg_no / registrations.registration_no
- 不把 methodology/storage_condition 强塞进 products 新列（优先 ivd_subtypes / product_params）
- 不改变前台默认 IVD-only 口径（products.is_ivd=true）

