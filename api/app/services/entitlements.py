from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Entitlements:
    can_export: bool
    max_subscriptions: int
    trend_range_days: int


@dataclass(frozen=True)
class MembershipInfo:
    plan: str
    plan_status: str
    plan_expires_at: datetime | None


def _normalize_text(v: object, default: str) -> str:
    if v is None:
        return default
    if not isinstance(v, str):
        return default
    s = v.strip().lower()
    return s or default


def get_membership_info(user) -> MembershipInfo:
    # Resilient for tests that use SimpleNamespace instead of SQLAlchemy model.
    plan = _normalize_text(getattr(user, 'plan', None), 'free')
    plan_status = _normalize_text(getattr(user, 'plan_status', None), 'inactive')
    plan_expires_at = getattr(user, 'plan_expires_at', None)
    return MembershipInfo(plan=plan, plan_status=plan_status, plan_expires_at=plan_expires_at)


def _is_pro_annual_active_not_expired(info: MembershipInfo, now: datetime) -> bool:
    if info.plan != 'pro_annual':
        return False
    if info.plan_status != 'active':
        return False
    if info.plan_expires_at is None:
        return False
    exp = info.plan_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > now


def get_entitlements(user, now: datetime | None = None) -> Entitlements:
    """
    Membership rules:
    - free / inactive:
      can_export=false
      max_subscriptions=3
      trend_range_days=30
    - pro_annual / active and not expired:
      can_export=true
      max_subscriptions=50
      trend_range_days=365
    - pro_annual / active but expired:
      treated as free (caller may refresh snapshot to inactive)
    """
    now0 = now or datetime.now(timezone.utc)
    info = get_membership_info(user)
    if _is_pro_annual_active_not_expired(info, now0):
        return Entitlements(can_export=True, max_subscriptions=50, trend_range_days=365)
    return Entitlements(can_export=False, max_subscriptions=3, trend_range_days=30)

