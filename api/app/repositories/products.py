from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from typing import Literal

from sqlalchemy import Select, String, and_, asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import ChangeLog, Company, Product

SortBy = Literal['updated_at', 'approved_date', 'expiry_date', 'name']
SortOrder = Literal['asc', 'desc']

_DATE_RANGE_DAYS: dict[str, int] = {
    '7d': 7,
    '30d': 30,
    '90d': 90,
    '12m': 365,
}

_CHANGE_TYPE_ALIASES: dict[str, str] = {
    'new': 'new',
    'create': 'new',
    '新增': 'new',
    'update': 'update',
    'change': 'update',
    'renew': 'update',
    '更新': 'update',
    'cancel': 'cancel',
    'cancelled': 'cancel',
    'remove': 'cancel',
    'removed': 'cancel',
    'expire': 'cancel',
    'expired': 'cancel',
    '注销': 'cancel',
}

_SORT_KEYS = {'recency', 'risk', 'lri', 'competition'}


def _normalize_date_range(value: str | None) -> str | None:
    raw = str(value or '').strip().lower()
    return raw if raw in _DATE_RANGE_DAYS else None


def _normalize_change_type(value: str | None) -> str | None:
    raw = str(value or '').strip().lower()
    if not raw:
        return None
    return _CHANGE_TYPE_ALIASES.get(raw)


def _normalize_sort(value: str | None) -> str | None:
    raw = str(value or '').strip().lower()
    return raw if raw in _SORT_KEYS else None


def _window_start(date_range: str | None) -> datetime | None:
    norm = _normalize_date_range(date_range)
    if not norm:
        return None
    return datetime.now(timezone.utc) - timedelta(days=_DATE_RANGE_DAYS[norm])


def _resolve_sort(sort: str | None, sort_by: SortBy, sort_order: SortOrder) -> tuple[SortBy, SortOrder]:
    norm = _normalize_sort(sort)
    if norm == 'recency':
        return 'updated_at', 'desc'
    return sort_by, sort_order


def build_search_query(
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
    track: str | None = None,
    change_type: str | None = None,
    date_range: str | None = None,
    ivd_filter: bool | None = True,
    include_unverified: bool = False,
) -> Select[tuple[Product]]:
    stmt = (
        select(Product)
        .options(joinedload(Product.company))
        .outerjoin(Company, Product.company_id == Company.id)
    )
    if ivd_filter is True:
        stmt = stmt.where(Product.is_ivd.is_(True))
    elif ivd_filter is False:
        stmt = stmt.where(Product.is_ivd.is_(False))
    if query:
        like = f'%{query}%'
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
    if status:
        stmt = stmt.where(Product.status == status)
    if track:
        track_like = f'%{track.strip()}%'
        stmt = stmt.where(
            or_(
                Product.ivd_category.ilike(track_like),
                Product.category.ilike(track_like),
                Product.class_name.ilike(track_like),
                Product.name.ilike(track_like),
            )
        )

    normalized_change_type = _normalize_change_type(change_type)
    window_start = _window_start(date_range)
    if normalized_change_type == 'new':
        if window_start is None:
            stmt = stmt.where(or_(Product.approved_date.is_not(None), Product.created_at.is_not(None)))
        else:
            stmt = stmt.where(
                or_(
                    Product.approved_date >= window_start.date(),
                    Product.created_at >= window_start,
                )
            )
    elif normalized_change_type == 'update':
        update_types = ('update', 'change', 'renew')
        update_conditions = [
            ChangeLog.product_id == Product.id,
            func.lower(func.coalesce(ChangeLog.change_type, '')).in_(update_types),
        ]
        if window_start is not None:
            update_conditions.append(ChangeLog.change_date >= window_start)
        update_exists = select(ChangeLog.id).where(and_(*update_conditions)).exists()
        if window_start is None:
            stmt = stmt.where(or_(update_exists, Product.updated_at.is_not(None)))
        else:
            stmt = stmt.where(or_(update_exists, Product.updated_at >= window_start))
    elif normalized_change_type == 'cancel':
        cancel_types = ('cancel', 'cancelled', 'remove', 'removed', 'expire', 'expired')
        cancel_conditions = [
            ChangeLog.product_id == Product.id,
            func.lower(func.coalesce(ChangeLog.change_type, '')).in_(cancel_types),
        ]
        if window_start is not None:
            cancel_conditions.append(ChangeLog.change_date >= window_start)
        cancel_exists = select(ChangeLog.id).where(and_(*cancel_conditions)).exists()
        cancelled_status = func.lower(func.coalesce(Product.status, '')).in_(('cancel', 'cancelled', 'revoked', 'invalid', '注销'))
        stmt = stmt.where(or_(cancelled_status, cancel_exists))

    # Default behavior: hide UDI stubs unless explicitly requested.
    # Stubs are marked by product.raw_json['_stub'].source_hint == 'UDI' and verified_by_nmpa == false.
    if not include_unverified:
        src = func.coalesce(Product.raw_json['_stub'].op('->>')('source_hint'), '')
        verified = func.coalesce(Product.raw_json['_stub'].op('->>')('verified_by_nmpa'), 'true')
        stmt = stmt.where(or_(src != 'UDI', verified == 'true'))
    return stmt


def search_products(
    db: Session,
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
    track: str | None,
    change_type: str | None,
    date_range: str | None,
    sort: str | None,
    include_unverified: bool,
    page: int,
    page_size: int,
    sort_by: SortBy,
    sort_order: SortOrder,
) -> tuple[list[Product], int]:
    base_stmt = build_search_query(
        query,
        company,
        reg_no,
        status,
        track=track,
        change_type=change_type,
        date_range=date_range,
        include_unverified=include_unverified,
    )
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0

    resolved_sort_by, resolved_sort_order = _resolve_sort(sort, sort_by, sort_order)
    sort_col = {
        'updated_at': Product.updated_at,
        'approved_date': Product.approved_date,
        'expiry_date': Product.expiry_date,
        'name': Product.name,
    }[resolved_sort_by]
    order_expr = asc(sort_col) if resolved_sort_order == 'asc' else desc(sort_col)

    stmt = base_stmt.order_by(order_expr, Product.id.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(stmt).unique().all())
    return items, total


def list_full_products(
    db: Session,
    *,
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
    include_unverified: bool,
    class_prefix: str | None,
    ivd_category: str | None,
    page: int,
    page_size: int,
    sort_by: SortBy,
    sort_order: SortOrder,
) -> tuple[list[Product], int]:
    stmt = build_search_query(query, company, reg_no, status, include_unverified=include_unverified)
    if class_prefix:
        stmt = stmt.where(Product.class_name.ilike(f'{class_prefix}%'))
    if ivd_category:
        stmt = stmt.where(Product.ivd_category == ivd_category)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    sort_col = {
        'updated_at': Product.updated_at,
        'approved_date': Product.approved_date,
        'expiry_date': Product.expiry_date,
        'name': Product.name,
    }[sort_by]
    order_expr = asc(sort_col) if sort_order == 'asc' else desc(sort_col)
    rows = db.scalars(stmt.order_by(order_expr, Product.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(rows.unique().all()), int(total)


def get_product(db: Session, product_id: str) -> Product | None:
    try:
        normalized_id = uuid.UUID(str(product_id))
    except (ValueError, TypeError):
        return None
    stmt = select(Product).options(joinedload(Product.company)).where(Product.id == normalized_id, Product.is_ivd.is_(True))
    return db.scalar(stmt)


def admin_search_products(
    db: Session,
    *,
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
    is_ivd: bool | None,
    ivd_category: str | None,
    ivd_version: str | None,
    page: int,
    page_size: int,
    sort_by: SortBy,
    sort_order: SortOrder,
) -> tuple[list[Product], int]:
    base_stmt = build_search_query(query, company, reg_no, status, ivd_filter=is_ivd)
    if ivd_category:
        base_stmt = base_stmt.where(Product.ivd_category == ivd_category)
    if ivd_version:
        # ivd_version is numeric in current schema; compare as string for compatibility.
        base_stmt = base_stmt.where(func.cast(Product.ivd_version, String) == str(ivd_version))
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    sort_col = {
        'updated_at': Product.updated_at,
        'approved_date': Product.approved_date,
        'expiry_date': Product.expiry_date,
        'name': Product.name,
    }[sort_by]
    order_expr = asc(sort_col) if sort_order == 'asc' else desc(sort_col)
    stmt = base_stmt.order_by(order_expr, Product.id.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(stmt).unique().all())
    return items, int(total)


def get_company(db: Session, company_id: str) -> Company | None:
    try:
        normalized_id = uuid.UUID(str(company_id))
    except (ValueError, TypeError):
        return None
    return db.get(Company, normalized_id)
