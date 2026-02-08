from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import DailyMetric


def _window_start(days: int) -> date:
    return date.today() - timedelta(days=max(days - 1, 0))


def get_summary(db: Session, days: int) -> tuple[date, date, int, int, int, int]:
    start_date = _window_start(days)
    end_date = date.today()

    stmt = (
        select(
            func.coalesce(func.sum(DailyMetric.new_products), 0),
            func.coalesce(func.sum(DailyMetric.updated_products), 0),
            func.coalesce(func.sum(DailyMetric.cancelled_products), 0),
        )
        .where(DailyMetric.metric_date >= start_date)
        .where(DailyMetric.metric_date <= end_date)
    )
    total_new, total_updated, total_removed = db.execute(stmt).one()

    latest_sub_stmt = (
        select(DailyMetric.active_subscriptions)
        .order_by(desc(DailyMetric.metric_date))
        .limit(1)
    )
    latest_active_subscriptions = db.scalar(latest_sub_stmt) or 0

    return start_date, end_date, int(total_new), int(total_updated), int(total_removed), int(latest_active_subscriptions)


def get_trend(db: Session, days: int) -> list[DailyMetric]:
    start_date = _window_start(days)
    stmt = (
        select(DailyMetric)
        .where(DailyMetric.metric_date >= start_date)
        .order_by(DailyMetric.metric_date.asc())
    )
    return list(db.scalars(stmt))


def get_rankings(db: Session, days: int, limit: int) -> tuple[list[tuple[date, int]], list[tuple[date, int]]]:
    start_date = _window_start(days)

    top_new_stmt = (
        select(DailyMetric.metric_date, DailyMetric.new_products)
        .where(DailyMetric.metric_date >= start_date)
        .order_by(desc(DailyMetric.new_products), desc(DailyMetric.metric_date))
        .limit(limit)
    )
    top_removed_stmt = (
        select(DailyMetric.metric_date, DailyMetric.cancelled_products)
        .where(DailyMetric.metric_date >= start_date)
        .order_by(desc(DailyMetric.cancelled_products), desc(DailyMetric.metric_date))
        .limit(limit)
    )

    return list(db.execute(top_new_stmt).all()), list(db.execute(top_removed_stmt).all())


def get_radar(db: Session) -> DailyMetric | None:
    stmt = select(DailyMetric).order_by(desc(DailyMetric.metric_date)).limit(1)
    return db.scalar(stmt)
