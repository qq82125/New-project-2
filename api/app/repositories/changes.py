from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import ChangeLog, Company, Product


def _since_days(days: int) -> datetime:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=int(days))


def get_change_stats(db: Session, *, days: int = 30) -> tuple[int, dict[str, int]]:
    since = _since_days(days)
    stmt = (
        select(ChangeLog.change_type, func.count(ChangeLog.id))
        .where(ChangeLog.change_date >= since)
        .group_by(ChangeLog.change_type)
    )
    rows = list(db.execute(stmt).all())
    by_type = {str(r[0]): int(r[1] or 0) for r in rows}
    total = int(sum(by_type.values()))
    return total, by_type


def list_recent_changes(
    db: Session,
    *,
    days: int = 30,
    limit: int = 50,
    page: int = 1,
    page_size: int | None = None,
    change_type: str | None = None,
    q: str | None = None,
    company: str | None = None,
    reg_no: str | None = None,
) -> tuple[list[tuple[ChangeLog, Product]], int]:
    since = _since_days(days)
    effective_page_size = max(1, int(page_size or limit or 50))
    effective_page = max(1, int(page or 1))
    base = (
        select(ChangeLog, Product)
        .join(Product, ChangeLog.product_id == Product.id)
        .where(
            ChangeLog.entity_type == 'product',
            ChangeLog.change_date >= since,
            Product.is_ivd.is_(True),
        )
    )
    count_stmt = (
        select(func.count(ChangeLog.id))
        .join(Product, ChangeLog.product_id == Product.id)
        .where(
            ChangeLog.entity_type == 'product',
            ChangeLog.change_date >= since,
            Product.is_ivd.is_(True),
        )
    )
    if change_type:
        tv = str(change_type).strip()
        base = base.where(ChangeLog.change_type == tv)
        count_stmt = count_stmt.where(ChangeLog.change_type == tv)
    if q:
        keyword = f'%{str(q).strip()}%'
        base = base.where(Product.name.ilike(keyword))
        count_stmt = count_stmt.where(Product.name.ilike(keyword))
    if reg_no:
        rv = f'%{str(reg_no).strip()}%'
        base = base.where(Product.reg_no.ilike(rv))
        count_stmt = count_stmt.where(Product.reg_no.ilike(rv))
    if company:
        cv = f'%{str(company).strip()}%'
        base = base.join(Company, Company.id == Product.company_id).where(Company.name.ilike(cv))
        count_stmt = count_stmt.join(Company, Company.id == Product.company_id).where(Company.name.ilike(cv))
    total = int(db.scalar(count_stmt) or 0)
    stmt = (
        base
        .order_by(desc(ChangeLog.change_date))
        .offset((effective_page - 1) * effective_page_size)
        .limit(effective_page_size)
    )
    return list(db.execute(stmt).all()), total


def list_changes_for_export(
    db: Session,
    *,
    days: int = 30,
    limit: int = 5000,
    change_type: str | None = None,
    q: str | None = None,
    company: str | None = None,
    reg_no: str | None = None,
) -> list[tuple[ChangeLog, Product]]:
    rows, _ = list_recent_changes(
        db,
        days=days,
        limit=max(1, int(limit)),
        page=1,
        page_size=max(1, int(limit)),
        change_type=change_type,
        q=q,
        company=company,
        reg_no=reg_no,
    )
    return rows


def get_change_detail(db: Session, *, change_id: int) -> ChangeLog | None:
    try:
        cid = int(change_id)
    except Exception:
        return None
    return db.get(ChangeLog, cid)
