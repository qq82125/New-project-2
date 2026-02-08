# PR5 Dashboard 前端（首页即看板）

## 页面
- `/` Dashboard
- `/search` Search
- `/products/[id]` Product Detail
- `/companies/[id]` Company Detail
- `/status` Status

## Dashboard 组件
- 同步状态条（来自 `/api/status`）
- KPI 卡片（来自 `/api/dashboard/summary`）
- 新增趋势图（来自 `/api/dashboard/trend`）
- 榜单
  - 新增产品（基于 `/api/search` 排序）
  - 企业榜单（基于 `/api/search` 结果聚合）
  - 即将到期（基于 `/api/search` 排序）
- 变更雷达列表（来自 `/api/dashboard/radar`）

## 状态处理
- loading：`/web/app/loading.tsx`
- empty：`EmptyState`
- error：`ErrorState` + `app/error.tsx`

## 交互
- 榜单点击支持跳转产品详情或带过滤条件的搜索页。
