from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import ChangeLog, Company, Product


def _since_days(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))


def list_company_tracking(
    db: Session,
    *,
    query: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    status_norm = func.lower(func.coalesce(Product.status, ''))
    is_expired = or_(status_norm == 'expired', Product.status == '过期')
    is_cancelled = or_(status_norm == 'cancelled', Product.status == '注销')
    is_active = ~(is_expired | is_cancelled)

    base = (
        select(
            Company.id.label('company_id'),
            Company.name.label('company_name'),
            Company.country.label('country'),
            func.count(Product.id).label('total_products'),
            func.sum(case((is_active, 1), else_=0)).label('active_products'),
            func.max(Product.updated_at).label('last_product_updated_at'),
        )
        .join(Product, Product.company_id == Company.id)
        .where(Product.is_ivd.is_(True))
        .group_by(Company.id, Company.name, Company.country)
    )
    if query:
        base = base.where(Company.name.ilike(f'%{query.strip()}%'))

    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(
        base.order_by(desc(func.count(Product.id)), Company.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items: list[dict] = []
    for r in rows:
        items.append(
            {
                'company_id': str(r.company_id),
                'company_name': str(r.company_name),
                'country': r.country,
                'total_products': int(r.total_products or 0),
                'active_products': int(r.active_products or 0),
                'last_product_updated_at': r.last_product_updated_at,
            }
        )
    return items, total


def get_company_tracking_detail(
    db: Session,
    *,
    company_id: str,
    days: int = 30,
    page: int = 1,
    page_size: int = 30,
) -> dict | None:
    try:
        cid = UUID(str(company_id))
    except Exception:
        return None

    company = db.get(Company, cid)
    if not company:
        return None

    has_ivd = db.scalar(
        select(func.count(Product.id)).where(Product.company_id == cid, Product.is_ivd.is_(True)).limit(1)
    )
    if not has_ivd:
        return None

    status_norm = func.lower(func.coalesce(Product.status, ''))
    is_expired = or_(status_norm == 'expired', Product.status == '过期')
    is_cancelled = or_(status_norm == 'cancelled', Product.status == '注销')
    is_active = ~(is_expired | is_cancelled)

    since = _since_days(days)
    prod_stats = db.execute(
        select(
            func.count(Product.id).label('total_products'),
            func.sum(case((is_active, 1), else_=0)).label('active_products'),
            func.sum(case((is_expired, 1), else_=0)).label('expired_products'),
            func.sum(case((is_cancelled, 1), else_=0)).label('cancelled_products'),
            func.max(Product.updated_at).label('last_product_updated_at'),
        ).where(Product.company_id == cid, Product.is_ivd.is_(True))
    ).one()

    chg_stats_rows = db.execute(
        select(ChangeLog.change_type, func.count(ChangeLog.id))
        .join(Product, Product.id == ChangeLog.product_id)
        .where(
            ChangeLog.entity_type == 'product',
            ChangeLog.change_date >= since,
            Product.company_id == cid,
            Product.is_ivd.is_(True),
        )
        .group_by(ChangeLog.change_type)
    ).all()
    by_type = {str(r[0]): int(r[1] or 0) for r in chg_stats_rows}
    total_changes = int(sum(by_type.values()))

    safe_page = max(1, int(page))
    safe_page_size = max(1, int(page_size))
    offset = (safe_page - 1) * safe_page_size

    recent_base = (
        select(ChangeLog, Product)
        .join(Product, Product.id == ChangeLog.product_id)
        .where(
            ChangeLog.entity_type == 'product',
            Product.company_id == cid,
            Product.is_ivd.is_(True),
        )
        .order_by(desc(ChangeLog.change_date))
    )
    recent_total = int(
        db.scalar(
            select(func.count(ChangeLog.id))
            .join(Product, Product.id == ChangeLog.product_id)
            .where(
                ChangeLog.entity_type == 'product',
                Product.company_id == cid,
                Product.is_ivd.is_(True),
            )
        )
        or 0
    )

    recent_rows = db.execute(
        recent_base
        .offset(offset)
        .limit(safe_page_size)
    ).all()

    recent_changes = []
    for change, product in recent_rows:
        recent_changes.append(
            {
                'id': int(change.id),
                'change_type': str(getattr(change, 'change_type', '') or ''),
                'change_date': getattr(change, 'change_date', None),
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'udi_di': product.udi_di,
                    'reg_no': product.reg_no,
                    'status': product.status,
                    'ivd_category': getattr(product, 'ivd_category', None),
                },
            }
        )

    return {
        'company': {
            'id': str(company.id),
            'name': company.name,
            'country': company.country,
        },
        'stats': {
            'days': int(days),
            'total_products': int(prod_stats.total_products or 0),
            'active_products': int(prod_stats.active_products or 0),
            'expired_products': int(prod_stats.expired_products or 0),
            'cancelled_products': int(prod_stats.cancelled_products or 0),
            'last_product_updated_at': prod_stats.last_product_updated_at,
            'changes_total': total_changes,
            'changes_by_type': by_type,
        },
        'recent_changes': recent_changes,
        'recent_changes_total': recent_total,
        'page': safe_page,
        'page_size': safe_page_size,
    }
