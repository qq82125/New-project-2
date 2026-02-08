from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.entitlements import get_entitlements


def test_entitlements_free_inactive() -> None:
    user = SimpleNamespace(plan='free', plan_status='inactive', plan_expires_at=None)
    ent = get_entitlements(user, now=datetime(2026, 2, 8, tzinfo=timezone.utc))
    assert ent.can_export is False
    assert ent.max_subscriptions == 3
    assert ent.trend_range_days == 30


def test_entitlements_pro_active_not_expired() -> None:
    now = datetime(2026, 2, 8, tzinfo=timezone.utc)
    user = SimpleNamespace(plan='pro_annual', plan_status='active', plan_expires_at=now + timedelta(days=1))
    ent = get_entitlements(user, now=now)
    assert ent.can_export is True
    assert ent.max_subscriptions == 50
    assert ent.trend_range_days == 365


def test_entitlements_pro_active_expired_treated_as_free() -> None:
    now = datetime(2026, 2, 8, tzinfo=timezone.utc)
    user = SimpleNamespace(plan='pro_annual', plan_status='active', plan_expires_at=now - timedelta(seconds=1))
    ent = get_entitlements(user, now=now)
    assert ent.can_export is False
    assert ent.max_subscriptions == 3
    assert ent.trend_range_days == 30

