from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import ChangeLog, Company, Product


def get_change_stats(db: Session, days: int = 30) -> tuple[int, dict[str, int]]:
    since = datetime.now(timezone.utc) - timedelta(days=int(days))
    base = select(ChangeLog).where(ChangeLog.change_date >= since)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    stmt = (
        select(ChangeLog.change_type, func.count())
        .where(ChangeLog.change_date >= since)
        .group_by(ChangeLog.change_type)
    )
    by_type = {str(k): int(v) for (k, v) in db.execute(stmt).all() if k is not None}
    return int(total), by_type


def list_recent_changes(
    db: Session,
    *,
    days: int = 30,
    page: int = 1,
    page_size: int = 20,
    change_type: str | None = None,
    q: str | None = None,
    company: str | None = None,
    reg_no: str | None = None,
) -> tuple[list[tuple[ChangeLog, Product]], int]:
    since = datetime.now(timezone.utc) - timedelta(days=int(days))
    stmt: Select = (
        select(ChangeLog, Product)
        .join(Product, ChangeLog.product_id == Product.id)
        .options(joinedload(Product.company))
        .outerjoin(Company, Product.company_id == Company.id)
        .where(ChangeLog.change_date >= since)
    )

    if change_type:
        stmt = stmt.where(ChangeLog.change_type == change_type)

    if q:
        like = f'%{q}%'
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.udi_di.ilike(like),
                Product.reg_no.ilike(like),
                Company.name.ilike(like),
            )
        )

    if company:
        stmt = stmt.where(Company.name.ilike(f'%{company}%'))
    if reg_no:
        stmt = stmt.where(Product.reg_no.ilike(f'%{reg_no}%'))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = (
        stmt.order_by(desc(ChangeLog.change_date), desc(ChangeLog.id))
        .offset((int(page) - 1) * int(page_size))
        .limit(int(page_size))
    )
    rows = list(db.execute(stmt).all())
    return [(c, p) for (c, p) in rows], int(total)

