# FRONTEND_UPGRADE_CONTRACT

## 1. 目标与硬约束
- 不修改数据库 schema。
- 不修改现有后端 API 返回结构。
- 不引入重型 UI 框架，复用现有 `web/components/ui/*` 与 Tailwind-less 样式体系（`web/app/globals.css`）。
- 保持登录/注册/Pro 锁/导出 CSV 现有能力可用。

## 2. 当前信息架构（基线）
- 公共壳层：`/Users/GY/Documents/New project 2/web/components/shell.tsx`
  - Header：品牌、主导航、登录态操作。
  - SideNav：业务入口与高级分析分组。
- 前台核心路由：
  - `/` Dashboard：`/Users/GY/Documents/New project 2/web/app/page.tsx`
  - `/search` Search：`/Users/GY/Documents/New project 2/web/app/search/page.tsx`
  - `/products/[id]` Detail：`/Users/GY/Documents/New project 2/web/app/products/[id]/page.tsx`
  - `/registrations/[registration_no]` Registration Detail：`/Users/GY/Documents/New project 2/web/app/registrations/[registration_no]/page.tsx`
  - `/subscriptions` 订阅与投递（占位）：`/Users/GY/Documents/New project 2/web/app/subscriptions/page.tsx`
  - `/pro` Pro 页面：`/Users/GY/Documents/New project 2/web/app/pro/page.tsx`
- Admin 路由：
  - `/admin`：`/Users/GY/Documents/New project 2/web/app/admin/page.tsx`
  - `/admin/*` 队列/配置页：`/Users/GY/Documents/New project 2/web/app/admin/*`

## 3. 页面清单与阶段范围
- Phase 1：
  - 主导航可见性与高亮。
  - Dashboard -> Search 三条可钻取链路。
  - Search 导出按钮统一 ProGate。
  - `/pro` 页面可访问并展示 Free vs Pro 对比。
- 后续 Phase（预留）：
  - Dashboard/Search/Detail 的统一标题、布局、状态机组件化。
  - Admin 队列可执行操作与原因码详情体验升级。

## 4. 统一状态机（页面级）
- `loading`：文案固定 `加载中…`
- `empty`：文案固定 `暂无数据`
- `error`：文案固定 `加载失败，请重试`
- 规则：
  - 不允许静默失败。
  - 错误必须通过页面状态组件或 Toast 可见。

## 5. 组件复用规范
- 基础 UI 组件：
  - 卡片：`/Users/GY/Documents/New project 2/web/components/ui/card.tsx`
  - 表格：`/Users/GY/Documents/New project 2/web/components/ui/table.tsx`
  - 按钮：`/Users/GY/Documents/New project 2/web/components/ui/button.tsx`
  - Badge：`/Users/GY/Documents/New project 2/web/components/ui/badge.tsx`
- 状态组件：
  - `LoadingState/EmptyState/ErrorState`：`/Users/GY/Documents/New project 2/web/components/States.tsx`
- Pro Gate：
  - 统一组件：`/Users/GY/Documents/New project 2/web/components/plan/UnifiedProGate.tsx`
  - Search 导出入口：`/Users/GY/Documents/New project 2/web/components/search/SearchExportActions.tsx`

## 6. URL 参数约定
- Search 支持：
  - `q` 关键字
  - `company` 企业名
  - `reg_no` 注册证号
  - `registration_no`（兼容别名，会映射到 `reg_no`）
  - `status`, `page`, `page_size`, `sort_by`, `sort_order`, `include_unverified`
- Dashboard 钻取约定：
  - LRI Top -> `/search?q={product_name}`
  - 高风险生命周期证 Top10 -> `/search?registration_no={registration_no}`
  - 高竞争格局证 Top10 -> `/search?q={track_name}`

## 7. Pro Gate 统一规范
- 标题：`升级到 Pro`
- 副标题：`解锁导出与高级分析能力`
- 权益对比：至少四条（导出 CSV / 订阅投递 / 高级筛选 / 风险信号）
- CTA：`联系开通` 与 `申请试用`，跳转 `/contact?intent=pro` 与 `/contact?intent=trial`

## 8. 不回归清单（每次提交执行）
- 未登录访问 `/`：保持当前重定向或引导行为。
- 登录后可进入 `/`，并可退出登录返回登录页。
- Free 用户：可访问 Dashboard/Search；导出 CSV 受 ProGate 约束。
- Pro 用户：导出 CSV 仍走原下载接口。
- `/admin`：非管理员无权限（重定向或提示一致）；管理员可正常访问。
- 每页具备 loading/empty/error 三态且错误可见。
