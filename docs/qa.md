# QA Self-Test Checklist (Free/Pro)

This checklist is for manual verification after changes to Free/Pro gating, plan display, and Pro-required API behavior.

## Preconditions
- Web: http://localhost:3000
- API: reachable via web proxy `/api/*`
- Prepare accounts:
  - Free user (plan not active)
  - Pro user (via membership grant or plan snapshot)
  - Admin user (role=admin)

## Free User
1) Login / Logout
- Login works: `/login` -> `/`
- Click top-right `退出` must redirect to `/login`
- After logout, refresh `/` should redirect to `/login` (no stale session)

2) Dashboard `/`
- Banner shows Free copy and CTA to `/contact?intent=trial`
- 新增产品榜单: only Top 5 visible + restricted hint at bottom
- 企业榜单: only Top 3 visible + restricted hint at bottom
- 即将到期榜单: does not show product list (shows summary/placeholder) + restricted hint at bottom
- Pro-only modules (e.g. 雷达/日榜): remain locked as before (no crash)

3) Left Nav
- Group `高级分析 (Pro)` shows locked items
- Hover: toast "升级 Pro 解锁"
- Click: toast + redirect to `/contact?intent=trial`

4) Search `/search`
- Results list only renders first 10 cards
- Under list shows hint "Free 仅展示前 10 条..." + CTA to `/contact?intent=trial`
- (Optional) Try requesting full mode directly:
  - `GET /api/search?mode=full` returns 403 with `detail.code=PRO_REQUIRED`

5) Product Detail `/products/{id}`
- Shows summary fields
- Shows "Free 仅展示摘要..." hint + CTA to `/contact?intent=trial`
- `GET /api/products/{id}?mode=full` returns 403 with `detail.code=PRO_REQUIRED`
- `GET /api/products/{id}/timeline` returns 403 with `detail.code=PRO_REQUIRED`

6) Status `/status`
- Shows "变化统计（近 30 天）" (counts by type)
- Does NOT show "变化列表（Pro）"
- Shows upgrade hint + CTA to `/contact?intent=trial`
- `GET /api/changes` returns 403 with `detail.code=PRO_REQUIRED`
- `GET /api/changes/{id}` returns 403 with `detail.code=PRO_REQUIRED`

7) Account `/account`
- Shows:
  - 当前计划: Free
  - plan_status
  - plan_expires_at: shows "以订阅为准/待配置" when null
- Shows upgrade button -> `/contact?intent=trial`

## Pro User (or Admin)
1) Dashboard `/`
- Banner shows Pro copy
- 新增产品榜单: shows full list (Top 10)
- 企业榜单: shows full list (Top 10)
- 即将到期榜单: shows product list (Top 10)

2) Left Nav
- `高级分析 (Pro)` items are clickable
- Click shows "即将上线" toast and does NOT redirect to trial

3) Search `/search`
- Results are not sliced by frontend limit (renders API results normally)
- No Free hint card under list
- `GET /api/search?mode=full` returns 200

4) Product Detail `/products/{id}`
- No Free hint card
- `GET /api/products/{id}?mode=full` returns 200
- `GET /api/products/{id}/timeline` returns 200 (may be empty)

5) Status `/status`
- Shows "变化统计"
- Shows "变化列表（Pro）" and can open details

6) Account `/account`
- Shows:
  - 当前计划: Pro
  - plan_status
  - plan_expires_at and remaining days (when available)

