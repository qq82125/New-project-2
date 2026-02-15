from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.models import DailyMetric, ProductRejected


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


def get_breakdown(db: Session, *, limit: int = 50) -> dict:
    """Inventory breakdown snapshot (IVD-only).

    We intentionally compute this from `products` (not `daily_metrics`) because it is a
    current-state snapshot, not a daily event metric.
    """
    limit0 = max(1, min(int(limit), 200))

    total_ivd = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS TRUE")).scalar() or 0)

    by_cat = list(
        db.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(ivd_category), ''), 'unknown') AS k, COUNT(1) AS v
                FROM products
                WHERE is_ivd IS TRUE
                GROUP BY 1
                ORDER BY v DESC, k ASC
                """
            )
        ).all()
    )

    by_src = list(
        db.execute(
            text(
                """
                SELECT
                  COALESCE(NULLIF(TRIM(COALESCE(raw_json->>'source', raw->>'source', 'unknown')), ''), 'unknown') AS k,
                  COUNT(1) AS v
                FROM products
                WHERE is_ivd IS TRUE
                GROUP BY 1
                ORDER BY v DESC, k ASC
                LIMIT :lim
                """
            ),
            {"lim": limit0},
        ).all()
    )

    return {
        "total_ivd_products": total_ivd,
        "by_ivd_category": [(str(r[0]), int(r[1])) for r in by_cat],
        "by_source": [(str(r[0]), int(r[1])) for r in by_src],
    }


def get_admin_stats(db: Session, *, limit: int = 50) -> dict:
    breakdown = get_breakdown(db, limit=int(limit))
    rejected_total = int(db.execute(text("SELECT COUNT(1) FROM products_rejected")).scalar() or 0)
    return {**breakdown, "rejected_total": rejected_total}
