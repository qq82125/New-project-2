from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChangeLog, DailyMetric, DailyUdiMetric, PendingUdiLink, Product, ProductUdiMap, SourceRun, Subscription, UdiDiMaster


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


def _count_total_di(db: Session) -> int:
    return int(db.scalar(select(func.count(UdiDiMaster.id))) or 0)


def _count_mapped_di(db: Session) -> int:
    # product_udi_map can contain multiple rows for same DI historically; dedupe on DI for coverage.
    return int(db.scalar(select(func.count(func.distinct(ProductUdiMap.di)))) or 0)


def _count_unmapped_di_pending(db: Session) -> int:
    # Pending queue status is uppercase in pending_udi_links; keep open alias for compatibility.
    return int(
        db.scalar(
            select(func.count(func.distinct(PendingUdiLink.di))).where(
                PendingUdiLink.status.in_(('PENDING', 'OPEN', 'pending', 'open'))
            )
        )
        or 0
    )


def generate_daily_metrics(db: Session, metric_date: date | None = None) -> DailyMetric:
    target_date = metric_date or date.today()

    new_products = _count_change_type(db, target_date, 'new')
    updated_products = _count_change_type(db, target_date, 'update')
    cancelled_products = _count_change_type(db, target_date, 'cancel') + _count_change_type(db, target_date, 'expire')
    expiring_in_90d = _count_expiring_in_90d(db, target_date)
    active_subscriptions = _count_active_subscriptions(db)
    source_run_id = _latest_source_run_id(db, target_date)
    total_di_count = _count_total_di(db)
    mapped_di_count = _count_mapped_di(db)
    unmapped_di_count = _count_unmapped_di_pending(db)
    coverage_ratio = (float(mapped_di_count) / float(total_di_count)) if total_di_count > 0 else 0.0

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

    udi_stmt = insert(DailyUdiMetric).values(
        metric_date=target_date,
        total_di_count=total_di_count,
        mapped_di_count=mapped_di_count,
        unmapped_di_count=unmapped_di_count,
        coverage_ratio=coverage_ratio,
        source_run_id=source_run_id,
    )
    udi_stmt = udi_stmt.on_conflict_do_update(
        index_elements=[DailyUdiMetric.metric_date],
        set_={
            'total_di_count': total_di_count,
            'mapped_di_count': mapped_di_count,
            'unmapped_di_count': unmapped_di_count,
            'coverage_ratio': coverage_ratio,
            'source_run_id': source_run_id,
        },
    )
    db.execute(udi_stmt)
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
