from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MembershipGrant, Subscription


@dataclass(frozen=True)
class PlanSnapshot:
    plan: str
    plan_status: str
    plan_expires_at: Optional[datetime]
    is_pro: bool
    is_admin: bool


def _norm_text(v: object, default: str) -> str:
    if not isinstance(v, str):
        return default
    s = v.strip().lower()
    return s or default


def _is_not_expired(expires_at: Optional[datetime], *, now: datetime) -> bool:
    if expires_at is None:
        return True
    exp = expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > now


def _has_active_membership_grant(db: Session, *, user_id: int, now: datetime) -> bool:
    """
    Uses membership_grants as the source of truth if present.
    A grant is considered active if: start_at <= now < end_at and plan indicates pro.
    """
    stmt = (
        select(MembershipGrant.id)
        .where(
            MembershipGrant.user_id == user_id,
            MembershipGrant.plan.in_(['pro', 'pro_annual']),
            MembershipGrant.start_at <= now,
            MembershipGrant.end_at > now,
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def _get_active_membership_grant_snapshot(
    db: Session,
    *,
    user_id: int,
    now: datetime,
) -> tuple[str, datetime] | None:
    """Returns the most-recent active pro grant snapshot (plan, end_at) if any."""
    stmt = (
        select(MembershipGrant.plan, MembershipGrant.end_at)
        .where(
            MembershipGrant.user_id == user_id,
            MembershipGrant.plan.in_(['pro', 'pro_annual']),
            MembershipGrant.start_at <= now,
            MembershipGrant.end_at > now,
        )
        .order_by(MembershipGrant.end_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    if not row:
        return None
    plan, end_at = row[0], row[1]
    if not isinstance(plan, str) or not isinstance(end_at, datetime):
        return None
    return plan, end_at


def _get_active_paid_subscription_expiry(db: Session, *, user, now: datetime) -> datetime | None:
    """Best-effort lookup against a paid subscription table.

    This codebase's `subscriptions` table is primarily used for product/webhook subscriptions,
    but the caller explicitly asked to prefer it if it contains more accurate paid plan data.

    To keep this safe and backward compatible, we only query it if it *looks* like a paid
    subscription table: it must have `status` and an expiry column.
    """

    try:
        cols = Subscription.__table__.c
    except Exception:
        return None

    # Detect common schema shapes.
    has_status = 'status' in cols
    exp_col = None
    for k in ('expires_at', 'expires_on', 'end_at', 'ends_at'):
        if k in cols:
            exp_col = cols[k]
            break

    if not has_status or exp_col is None:
        return None

    # Identify the owner column.
    owner_filter = None
    if 'user_id' in cols:
        try:
            uid = int(getattr(user, 'id', 0) or 0)
        except Exception:
            uid = 0
        if not uid:
            return None
        owner_filter = cols['user_id'] == uid
    elif 'subscriber_key' in cols:
        email = getattr(user, 'email', None)
        if not isinstance(email, str) or not email.strip():
            return None
        owner_filter = cols['subscriber_key'] == email.strip()
    else:
        return None

    stmt = (
        select(exp_col)
        .where(
            owner_filter,
            func.lower(cols['status']) == 'active',
            exp_col.is_(None) | (exp_col > now),
        )
        .order_by(exp_col.desc())
        .limit(1)
    )
    try:
        v = db.scalar(stmt)
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        # date-like: promote to datetime at UTC midnight
        try:
            from datetime import date as date_type

            if isinstance(v, date_type):
                return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        except Exception:
            pass
        return None
    except Exception:
        return None


def compute_plan(user, db: Session, *, now: datetime | None = None) -> PlanSnapshot:
    """
    Single source of truth for plan computation.

    Rules (as requested):
    - role == 'admin' => is_pro = True
    - else if there's an active paid subscription in DB => True
    - else if there's an active membership grant in DB => True
    - else fallback to users.* snapshot:
      users.plan in ('pro','pro_annual') and plan_status in ('active','trial') and not expired => True
    - else False
    """
    now0 = now or datetime.now(timezone.utc)

    role = _norm_text(getattr(user, 'role', None), 'user')
    is_admin = role == 'admin'

    plan = _norm_text(getattr(user, 'plan', None), 'free')
    plan_status = _norm_text(getattr(user, 'plan_status', None), 'inactive')
    plan_expires_at = getattr(user, 'plan_expires_at', None)

    if is_admin:
        return PlanSnapshot(
            plan=plan,
            plan_status=plan_status,
            plan_expires_at=plan_expires_at,
            is_pro=True,
            is_admin=True,
        )

    is_pro = False
    try:
        user_id = int(getattr(user, 'id', 0) or 0)
    except Exception:
        user_id = 0

    # Prefer paid subscription table if present (best-effort).
    paid_exp = _get_active_paid_subscription_expiry(db, user=user, now=now0)
    if paid_exp is not None:
        return PlanSnapshot(
            plan='pro',
            plan_status='active',
            plan_expires_at=paid_exp,
            is_pro=True,
            is_admin=False,
        )

    # Prefer membership grants (source of truth in this project).
    if user_id:
        try:
            snap = _get_active_membership_grant_snapshot(db, user_id=user_id, now=now0)
            if snap is not None:
                grant_plan, grant_end_at = snap
                return PlanSnapshot(
                    plan=_norm_text(grant_plan, 'pro'),
                    plan_status='active',
                    plan_expires_at=grant_end_at,
                    is_pro=True,
                    is_admin=False,
                )
        except Exception:
            # Never 500 due to plan computation. Fall back to user snapshot.
            pass

    if not is_pro:
        if plan in {'pro', 'pro_annual'} and plan_status in {'active', 'trial'} and _is_not_expired(plan_expires_at, now=now0):
            is_pro = True

    return PlanSnapshot(
        plan=plan,
        plan_status=plan_status,
        plan_expires_at=plan_expires_at,
        is_pro=is_pro,
        is_admin=False,
    )
