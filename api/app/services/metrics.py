from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChangeLog, DailyMetric, Product, SourceRun, Subscription


def _count_change_type(db: Session, metric_date: date, change_type: str) -> int:
    stmt = (
        select(func.count(ChangeLog.id))
        .join(Product, Product.id == ChangeLog.product_id)
        .where(
            ChangeLog.change_date >= metric_date,
            ChangeLog.change_date < metric_date + timedelta(days=1),
            ChangeLog.change_type == change_type,
            Product.is_ivd.is_(True),
        )
    )
    return int(db.scalar(stmt) or 0)


def _count_expiring_in_90d(db: Session, metric_date: date) -> int:
    upper = metric_date + timedelta(days=90)
    stmt = select(func.count(Product.id)).where(
        Product.expiry_date.is_not(None),
        Product.expiry_date >= metric_date,
        Product.expiry_date <= upper,
        Product.status != 'cancelled',
        Product.is_ivd.is_(True),
    )
    return int(db.scalar(stmt) or 0)


def _count_active_subscriptions(db: Session) -> int:
    stmt = select(func.count(Subscription.id)).where(Subscription.is_active.is_(True))
    return int(db.scalar(stmt) or 0)


def _latest_source_run_id(db: Session, metric_date: date) -> int | None:
    stmt = (
        select(SourceRun.id)
        .where(SourceRun.started_at >= metric_date, SourceRun.started_at < metric_date + timedelta(days=1))
        .order_by(SourceRun.started_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def generate_daily_metrics(db: Session, metric_date: date | None = None) -> DailyMetric:
    target_date = metric_date or date.today()

    new_products = _count_change_type(db, target_date, 'new')
    updated_products = _count_change_type(db, target_date, 'update')
    cancelled_products = _count_change_type(db, target_date, 'cancel') + _count_change_type(db, target_date, 'expire')
    expiring_in_90d = _count_expiring_in_90d(db, target_date)
    active_subscriptions = _count_active_subscriptions(db)
    source_run_id = _latest_source_run_id(db, target_date)

    stmt = insert(DailyMetric).values(
        metric_date=target_date,
        new_products=new_products,
        updated_products=updated_products,
        cancelled_products=cancelled_products,
        expiring_in_90d=expiring_in_90d,
        active_subscriptions=active_subscriptions,
        source_run_id=source_run_id,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyMetric.metric_date],
        set_={
            'new_products': new_products,
            'updated_products': updated_products,
            'cancelled_products': cancelled_products,
            'expiring_in_90d': expiring_in_90d,
            'active_subscriptions': active_subscriptions,
            'source_run_id': source_run_id,
        },
    )
    db.execute(stmt)
    db.commit()

    row = db.get(DailyMetric, target_date)
    if row is None:
        raise RuntimeError('failed to upsert daily_metrics')
    return row


def regenerate_daily_metrics(db: Session, *, days: int = 365, end_date: date | None = None) -> list[str]:
    if days <= 0:
        return []
    end0 = end_date or date.today()
    start0 = end0 - timedelta(days=days - 1)
    out: list[str] = []
    cur = start0
    while cur <= end0:
        row = generate_daily_metrics(db, cur)
        out.append(row.metric_date.isoformat())
        cur = cur + timedelta(days=1)
    return out
