from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class GrantWindow:
    start_at: datetime
    end_at: datetime


def add_months(dt: datetime, months: int) -> datetime:
    if months <= 0:
        raise ValueError('months must be > 0')

    # Preserve timezone; treat naive as UTC to avoid crashing.
    tz = dt.tzinfo or timezone.utc
    base = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    y = base.year
    m0 = base.month - 1 + months
    y += m0 // 12
    m = (m0 % 12) + 1

    last_day = calendar.monthrange(y, m)[1]
    d = min(base.day, last_day)
    return base.replace(year=y, month=m, day=d, tzinfo=tz)


def is_active_pro_annual(user, now: datetime | None = None) -> bool:
    now0 = now or datetime.now(timezone.utc)
    plan = (getattr(user, 'plan', None) or 'free').strip().lower()
    status = (getattr(user, 'plan_status', None) or 'inactive').strip().lower()
    exp = getattr(user, 'plan_expires_at', None)
    if plan != 'pro_annual' or status != 'active' or exp is None:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > now0


def compute_grant_window(months: int, start_at: datetime | None = None, now: datetime | None = None) -> GrantWindow:
    now0 = now or datetime.now(timezone.utc)
    s = start_at or now0
    if s.tzinfo is None:
        s = s.replace(tzinfo=timezone.utc)
    e = add_months(s, months)
    return GrantWindow(start_at=s, end_at=e)


def compute_extend_window(months: int, current_expires_at: datetime | None, now: datetime | None = None) -> GrantWindow:
    now0 = now or datetime.now(timezone.utc)
    base = current_expires_at
    if base is None:
        base = now0
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if base <= now0:
        base = now0
    e = add_months(base, months)
    return GrantWindow(start_at=base, end_at=e)

