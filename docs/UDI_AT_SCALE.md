# UDI At Scale

## 目标
在不破坏现有 schema 语义的前提下，支持 UDI 多规格场景下的稳定映射与人工闭环。

核心原则：
1. `registration_no` 是锚点，`di` 是规格层标识。
2. `udi_di_master` 必须全量记录 DI（无论是否可映射）。
3. `product_udi_map` 是可消费映射层，区分 `match_type=direct/manual`。
4. 无法解析到注册证号时进入 `pending_udi_links`，不污染主表。

## 写入规则
### A. 有 `registration_no`
1. `normalize_registration_no`
2. `upsert registrations`
3. 写 `product_udi_map(registration_no, di, match_type='direct', confidence=0.95)`
4. 若存在同 DI 的 pending，标记为 `RESOLVED`

### B. 无 `registration_no` 或解析失败
1. 写 `raw_source_records`
2. 写 `udi_di_master`
3. 写 `pending_udi_links`：
   - `di`
   - `reason_code`
   - `raw_id` / `raw_source_record_id`
   - `candidate_company_name`
   - `candidate_product_name`
   - `status=PENDING`

### C. 人工绑定
后台接口将 `pending_udi_links` 手工绑定到 `registration_no`：
1. `upsert registrations`
2. 写 `product_udi_map(..., match_type='manual')`
3. 更新 pending 为 `RESOLVED`，记录 `resolved_at/resolved_by`

## 质量审计
脚本：
```bash
python scripts/udi_link_audit.py --dry-run --threshold 20
```

输出：
1. 每个 `registration_no` 的 DI 数量分布（P50/P90/P99）
2. 超阈值证号清单
3. 同一 DI 绑定多个证号的冲突清单

## 索引建议
已建议/使用索引：
1. `udi_di_master(di unique)`
2. `product_udi_map(registration_no)`
3. `product_udi_map(di)`
4. `product_udi_map(match_type)`
5. `pending_udi_links(status, created_at desc)`
6. `pending_udi_links(di)`
7. `pending_udi_links(reason_code)`
8. `pending_udi_links(resolved_at desc)`

## 风险与约束
1. 历史数据可能存在同 DI 多证号冲突，建议先审计再强约束。
2. `manual` 绑定优先级高于 `direct`，避免自动流程覆盖人工修正。
3. 所有映射变更应保留证据链（`raw_source_record_id` + `change_log`）。

