# PR4 FastAPI 接口层

## 范围
- Dashboard API
  - `GET /api/dashboard/summary`
  - `GET /api/dashboard/trend`
  - `GET /api/dashboard/rankings`
  - `GET /api/dashboard/radar`
- 搜索 API
  - `GET /api/search`
- 详情 API
  - `GET /api/products/{id}`
  - `GET /api/companies/{id}`
- 同步状态
  - `GET /api/status`

## 统一返回口径
所有接口返回：
```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

## 参数规范
- `/api/search`
  - 过滤：`q`, `company`, `reg_no`, `status`
  - 分页：`page`, `page_size`
  - 排序：`sort_by` (`updated_at|approved_date|expiry_date|name`), `sort_order` (`asc|desc`)

## 性能约束
- Dashboard 查询基于 `daily_metrics` 聚合与日期窗口，不做全表扫描 products。
- 搜索使用 `ILIKE` 模糊匹配（配合 `pg_trgm` 索引）。

## 错误码
- `404`：资源不存在（product/company）
- `422`：参数校验失败（如 `page=0`）
- `500`：未捕获异常（FastAPI 默认）
