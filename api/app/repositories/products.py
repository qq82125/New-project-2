from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Company, Product

SortBy = Literal['updated_at', 'approved_date', 'expiry_date', 'name']
SortOrder = Literal['asc', 'desc']


def build_search_query(
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
) -> Select[tuple[Product]]:
    stmt = (
        select(Product)
        .options(joinedload(Product.company))
        .outerjoin(Company, Product.company_id == Company.id)
    )
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
    return stmt


def search_products(
    db: Session,
    query: str | None,
    company: str | None,
    reg_no: str | None,
    status: str | None,
    page: int,
    page_size: int,
    sort_by: SortBy,
    sort_order: SortOrder,
) -> tuple[list[Product], int]:
    base_stmt = build_search_query(query, company, reg_no, status)
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
    return items, total


def get_product(db: Session, product_id: str) -> Product | None:
    try:
        normalized_id = uuid.UUID(str(product_id))
    except (ValueError, TypeError):
        return None
    stmt = select(Product).options(joinedload(Product.company)).where(Product.id == normalized_id)
    return db.scalar(stmt)


def get_company(db: Session, company_id: str) -> Company | None:
    try:
        normalized_id = uuid.UUID(str(company_id))
    except (ValueError, TypeError):
        return None
    return db.get(Company, normalized_id)
