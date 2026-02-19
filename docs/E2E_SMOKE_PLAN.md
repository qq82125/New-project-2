# E2E Smoke Plan (By TestID)

## Purpose
Use stable `data-testid` selectors to run manual smoke checks for Snapshot Map P0-P6.

## Pre-check
1. Start services: `docker compose up -d --build`
2. Open app: `http://localhost:3000`
3. Prepare one Free account and one Pro/Admin account.

## P0 Login `/login`
- Check `[data-testid="login__header__title"]`
- Check `[data-testid="login__header__form"]`
- Check `[data-testid="login__header__submit"]`
- Check `[data-testid="login__header__to_register"]`

## P1 Dashboard `/`
- Check `[data-testid="dashboard__header__nav"]`
- Check `[data-testid="dashboard__kpi__panel"]`
- Check at least one `[data-testid="dashboard__kpi__card"]`
- Check `[data-testid="dashboard__kpi__view_list"]`
- Check `[data-testid="dashboard__lri_top__panel"]`
- Check `[data-testid="dashboard__lri_top__row_1"]`
- Check `[data-testid="dashboard__risk_top__panel"]`
- Check `[data-testid="dashboard__risk_top__row_1"]`
- Check `[data-testid="dashboard__competitive_top__panel"]`
- Check `[data-testid="dashboard__competitive_top__row_1"]`
- Check `[data-testid="dashboard__trend__panel"]`
- Check `[data-testid="dashboard__trend__tab"]`
- Check `[data-testid="dashboard__lri_map__panel"]`
- Check `[data-testid="dashboard__lri_map__view_track"]`

## P2 Search `/search`
- Check `[data-testid="search__header__title"]`
- Check `[data-testid="search__filters__panel"]`
- Check `[data-testid="search__filters__basic_toggle"]`
- Check `[data-testid="search__filters__scope_toggle"]`
- Check `[data-testid="search__filters__include_pending"]`
- Check `[data-testid="search__saved_views__panel"]`
- Check `[data-testid="search__saved_views__save"]`
- Check `[data-testid="search__saved_views__select"]`
- Check `[data-testid="search__results__list"]`
- Check `[data-testid="search__results__row_1"]`
- Check `[data-testid="search__export__button"]`
- Free user click export and check `[data-testid="progate__cta__panel"]`

## P3 Detail `/products/[id]` or `/registrations/[no]`
- Check `[data-testid="detail__overview__panel"]`
- Check `[data-testid="detail__overview__registration_no"]`
- Check `[data-testid="detail__fields__panel"]`
- Check `[data-testid="detail__evidence__panel"]`
- Check `[data-testid="detail__timeline__panel"]`
- If present check `[data-testid="detail__header__back"]`

## P4 Admin `/admin`
- Check `[data-testid="admin__header__title"]`
- Check `[data-testid="admin__nav__panel"]`
- Check `[data-testid="admin__cards__panel"]`
- Check `[data-testid="admin__cards__pending_docs"]`
- Check `[data-testid="admin__cards__udi_pending"]`
- Check `[data-testid="admin__cards__conflicts"]`
- Check `[data-testid="admin__cards__high_risk"]`
- Check `[data-testid="admin__reason_top__panel"]`

## P5 Admin Queue `/admin/queue/*`
For each queue page:
- Check `[data-testid="admin_queue__header__title"]`
- Check `[data-testid="admin_queue__filters__panel"]`
- Check `[data-testid="admin_queue__list__panel"]`
- Check `[data-testid="admin_queue__bulk__panel"]`
- If present check `[data-testid="admin_queue__list__load_more"]`

## P6 Reason Detail `/admin/reasons/[code]`
- Check `[data-testid="admin_reason__header__title"]`
- Check `[data-testid="admin_reason__sample__list"]`
- Check `[data-testid="admin_reason__sample__copy_ticket"]`
