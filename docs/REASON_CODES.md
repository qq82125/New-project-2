# REASON_CODES

本文档定义 ingestion 质量队列中常见 `reason_code` 的含义、触发条件与修复建议。

## REGNO_MISSING
- 触发条件:
  - `registration_no` 原值缺失；或
  - `normalize_registration_no()` 后为空（无可用规范化结果）。
- 影响:
  - 阻断 `registrations/products` 主表结构化写入；
  - 仅保留证据链（如 `raw_documents` / `raw_source_records`）；
  - 写入 Admin 可见队列（`pending_records` / `pending_documents` / `pending_udi_links`）。
- 修复建议:
  - 回查上游源字段映射（`registration_no/reg_no/registry_no`）；
  - 补录可识别注册证号后重跑该记录。

## REGNO_PARSE_FAILED
- 触发条件:
  - `normalize_registration_no()` 有值；
  - 但 `parse_registration_no(...).parse_ok == false`（语义格式不符合已支持规则）。
- 影响:
  - 阻断 `registrations/products` 主表结构化写入；
  - 仅保留证据链并进入 Admin 质量队列。
- 修复建议:
  - 核对注册证号是否被截断/拼接污染；
  - 若为新合法格式，补充解析器规则后重放数据。

## REGISTRATION_NO_NOT_FOUND
- 触发条件:
  - 证号存在但无法完成目标映射（如 UDI 绑定阶段未命中注册锚点）。
- 影响:
  - 记录进入待处理队列，等待人工或后续规则补链。
- 修复建议:
  - 检查证号一致性、数据时效与来源优先级；
  - 必要时在 Admin 侧手动绑定。

## 历史兼容码
- `NO_REG_NO`、`PARSE_ERROR` 仍可能在历史数据或旧流程中出现。
- 新增质量门禁流程优先使用 `REGNO_MISSING` / `REGNO_PARSE_FAILED`。
