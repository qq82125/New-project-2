from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import MembershipEvent, MembershipGrant, User
from app.services.membership_admin import compute_extend_window, compute_grant_window, is_active_pro_annual


def admin_list_users(db: Session, *, query: str | None, limit: int, offset: int) -> list[User]:
    stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    if query:
        q = query.strip()
        if q:
            stmt = (
                select(User)
                .where(or_(User.email.ilike(f'%{q}%'), User.role.ilike(f'%{q}%')))
                .order_by(desc(User.created_at))
                .limit(limit)
                .offset(offset)
            )
    return list(db.scalars(stmt).all())


def admin_get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def admin_list_recent_grants(db: Session, *, user_id: int, limit: int) -> list[MembershipGrant]:
    stmt = (
        select(MembershipGrant)
        .where(MembershipGrant.user_id == user_id)
        .order_by(desc(MembershipGrant.created_at), desc(MembershipGrant.id))
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _create_event(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> MembershipEvent:
    ev = MembershipEvent(
        user_id=user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(ev)
    return ev


def _create_grant(
    db: Session,
    *,
    user_id: int,
    granted_by_user_id: int,
    plan: str,
    start_at: datetime,
    end_at: datetime,
    reason: str | None,
    note: str | None,
) -> MembershipGrant:
    g = MembershipGrant(
        user_id=user_id,
        granted_by_user_id=granted_by_user_id,
        plan=plan,
        start_at=start_at,
        end_at=end_at,
        reason=reason,
        note=note,
    )
    db.add(g)
    return g


def admin_grant_membership(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    plan: str,
    months: int,
    start_at: datetime | None,
    reason: str | None,
    note: str | None,
) -> User | None:
    now = datetime.now(timezone.utc)
    with db.begin():
        user = db.get(User, user_id)
        if not user:
            return None
        if is_active_pro_annual(user, now=now):
            # Caller should use extend instead.
            raise ValueError('already_active_pro')

        win = compute_grant_window(months=months, start_at=start_at, now=now)
        _create_grant(
            db,
            user_id=user_id,
            granted_by_user_id=actor_user_id,
            plan=plan,
            start_at=win.start_at,
            end_at=win.end_at,
            reason=reason,
            note=note,
        )
        _create_event(
            db,
            user_id=user_id,
            actor_user_id=actor_user_id,
            event_type='grant',
            payload={
                'plan': plan,
                'months': months,
                'start_at': win.start_at.isoformat(),
                'end_at': win.end_at.isoformat(),
                'reason': reason,
                'note': note,
            },
        )

        user.plan = plan
        user.plan_status = 'active'
        user.plan_expires_at = win.end_at
        db.add(user)
    db.refresh(user)  # type: ignore[arg-type]
    return user


def admin_extend_membership(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    months: int,
    reason: str | None,
    note: str | None,
) -> User | None:
    now = datetime.now(timezone.utc)
    with db.begin():
        user = db.get(User, user_id)
        if not user:
            return None
        win = compute_extend_window(months=months, current_expires_at=getattr(user, 'plan_expires_at', None), now=now)

        _create_grant(
            db,
            user_id=user_id,
            granted_by_user_id=actor_user_id,
            plan='pro_annual',
            start_at=win.start_at,
            end_at=win.end_at,
            reason=reason,
            note=note,
        )
        _create_event(
            db,
            user_id=user_id,
            actor_user_id=actor_user_id,
            event_type='extend',
            payload={
                'months': months,
                'start_at': win.start_at.isoformat(),
                'end_at': win.end_at.isoformat(),
                'reason': reason,
                'note': note,
            },
        )

        user.plan = 'pro_annual'
        user.plan_status = 'active'
        user.plan_expires_at = win.end_at
        db.add(user)
    db.refresh(user)  # type: ignore[arg-type]
    return user


def admin_suspend_membership(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    reason: str | None,
    note: str | None,
) -> User | None:
    with db.begin():
        user = db.get(User, user_id)
        if not user:
            return None
        prev = {'plan': user.plan, 'plan_status': user.plan_status, 'plan_expires_at': user.plan_expires_at}

        user.plan_status = 'suspended'
        db.add(user)

        _create_event(
            db,
            user_id=user_id,
            actor_user_id=actor_user_id,
            event_type='suspend',
            payload={'prev': _jsonable(prev), 'reason': reason, 'note': note},
        )
    db.refresh(user)  # type: ignore[arg-type]
    return user


def admin_revoke_membership(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    reason: str | None,
    note: str | None,
) -> User | None:
    with db.begin():
        user = db.get(User, user_id)
        if not user:
            return None
        prev = {'plan': user.plan, 'plan_status': user.plan_status, 'plan_expires_at': user.plan_expires_at}

        user.plan = 'free'
        user.plan_status = 'inactive'
        user.plan_expires_at = None
        db.add(user)

        _create_event(
            db,
            user_id=user_id,
            actor_user_id=actor_user_id,
            event_type='revoke',
            payload={'prev': _jsonable(prev), 'reason': reason, 'note': note},
        )
    db.refresh(user)  # type: ignore[arg-type]
    return user


def _jsonable(v: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, val in v.items():
        if isinstance(val, datetime):
            out[k] = val.isoformat()
        else:
            out[k] = val
    return out

