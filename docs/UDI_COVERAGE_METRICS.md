# UDI 映射覆盖率指标口径

## 落库位置
- 使用新增表：`daily_udi_metrics`
- 不修改既有 `daily_metrics` 字段语义
- 由同一日任务入口重算：`python -m app.workers.cli daily-metrics --date YYYY-MM-DD`
- 批量重算沿用：`python -m app.workers.cli metrics:recompute --since YYYY-MM-DD`

## 指标定义（每日快照）
- `total_di_count`：`udi_di_master` 中 DI 总数
- `mapped_di_count`：`product_udi_map` 已绑定 DI 去重数（`COUNT(DISTINCT di)`）
- `unmapped_di_count`：`pending_udi_links` 中 open/pending 状态 DI 去重数
- `coverage_ratio`：`mapped_di_count / total_di_count`（`total_di_count=0` 时为 `0`）

## SQL 口径（权威）
```sql
-- total_di_count
SELECT COUNT(*) FROM udi_di_master;

-- mapped_di_count
SELECT COUNT(DISTINCT di) FROM product_udi_map;

-- unmapped_di_count
SELECT COUNT(DISTINCT di)
FROM pending_udi_links
WHERE status IN ('PENDING', 'OPEN', 'pending', 'open');

-- coverage_ratio
SELECT CASE
         WHEN total_di_count > 0 THEN mapped_di_count::numeric / total_di_count::numeric
         ELSE 0
       END AS coverage_ratio;
```

## 说明
- `mapped_di_count` 与 `unmapped_di_count` 都按 `DI` 去重，避免重复记录导致口径漂移。
- 日指标是“当天计算时点快照”，不按历史回放 DI 事件做时序还原。
