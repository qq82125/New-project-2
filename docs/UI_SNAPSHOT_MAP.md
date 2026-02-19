# UI_SNAPSHOT_MAP

说明：本清单用于人工验收与后续 E2E。状态以当前 `main` 分支为准；如有待合并修复，单独标注 PR。

## 总览状态（P0-P6）
| 点位 | 状态 | 结论 |
|---|---|---|
| P0 登录页（/login） | ✅ 已完成 | 登录表单、注册入口、文案可见。 |
| P1 Dashboard（/） | ⚠️ 部分完成 | 已完成主导航与多条钻取；缺失项：`查看全部/查看列表` 文案统一、趋势 Tab 与 LRI Map 行动按钮未完全对齐规范。 |
| P2 Search（/search） | ⚠️ 部分完成 | 筛选分组、URL 恢复、Saved Views、本地导出 ProGate 已实现；缺失项：筛选区位置（左侧）与 Saved Views 的“管理入口”样式未完全统一。 |
| P3 Detail（/products/[id], /registrations/[no]） | ✅ 已完成 | 概览、结构化分组折叠、证据与变更三态、返回路径均已落地。 |
| P4 Admin（/admin） | ✅ 已完成 | 导航分组、四块队列卡片可点击、原因码 TOP 入口可用。 |
| P5 Admin 队列页（/admin/queue/*） | ⚠️ 部分完成 | 四个队列页可用并具备筛选/加载更多/批量/下钻；缺失项：H1 与首屏 empty/error 展示一致性修正待合并 PR#1。 |
| P6 原因码详情（/admin/reasons/[code]） | ✅ 已完成 | 统计、10 条样本、复制工单文本（含 reason_code/sample_ids/复现路径/建议修复点）已实现。 |

## 详细点位

### P0 登录页（/login）
- 状态：✅ 已完成
- 区域：页面主体表单区域
- 关键元素：邮箱输入、密码输入、登录按钮、去注册入口
- 文案：`登录`、`没有账号？去注册`

### P1 Dashboard（/）
- 状态：⚠️ 部分完成
- 已完成：
  - Header 导航（`仪表盘`、`搜索`、`订阅与投递`、`Admin` 管理员可见）
  - 当前页高亮
  - LRI Top / 高风险生命周期证 / 高竞争格局证 的首行钻取
- 缺失项：
  - `查看全部/查看列表` 操作位与统一文案未全部补齐
  - 趋势图 Tab（新增/更新/注销）与 hover tooltip 未统一
  - LRI Map 的“查看该赛道产品”按钮未按点位标准固化

### P2 Search（/search）
- 状态：⚠️ 部分完成
- 已完成：
  - 筛选区分组（基础/口径/风险）与折叠
  - URL 参数恢复（含 `include_pending`）
  - Saved Views（保存/恢复/删除，本地存储）
  - 导出 CSV：Free 弹统一 ProGate，Pro 保持原下载逻辑
- 缺失项：
  - 筛选区左侧布局与顶部布局仍混用（当前以顶部为主）
  - Saved Views 的“管理入口”交互为最小实现，未做独立管理面板

### P3 Detail（/products/[id] 或 /registrations/[no]）
- 状态：✅ 已完成
- 已完成：
  - 概览区（名称/企业/注册证号可复制/状态/关键日期）
  - 结构化字段分组折叠（>=3 组）+ 长文本 `show more`
  - 证据与变更区三态（有数据/空/错误）
  - 返回路径保留 Search query

### P4 Admin（/admin）
- 状态：✅ 已完成
- 已完成：
  - Admin 导航分组（数据质量/风险运营/系统）
  - 四块队列卡片入口
  - 原因码 TOP 可进入详情

### P5 Admin 队列页（/admin/queue/*）
- 状态：⚠️ 部分完成
- 已完成：
  - 每个队列页具备筛选 + 加载更多 + 批量操作 + drill down
- 缺失项：
  - 队列页顶部 H1 与首屏 empty/error 一致性改进待合并 PR#1（`fix/admin-queues-wireup`）

### P6 原因码详情（/admin/reasons/[code]）
- 状态：✅ 已完成
- 已完成：
  - reason_code、统计数、10 条样本
  - `复制工单文本` 按钮
  - 复制内容包含：`reason_code`、`sample_ids(>=3)`、复现路径、建议修复点

## 待合并 PR 影响
- PR#1：`fix/admin-queues-wireup`（队列页 H1 与 empty/error 首屏一致性）
- PR#2：`fix/pro-page`（`/pro` 标题与定价页布局完善、ProGate 到 `/pro` 入口）
