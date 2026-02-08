from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Company, Product, Registration


def build_search_query(
    query: str | None,
    company: str | None,
    registration_no: str | None,
) -> Select[tuple[Product]]:
    stmt = (
        select(Product)
        .options(joinedload(Product.company), joinedload(Product.registration))
        .outerjoin(Company, Product.company_id == Company.id)
        .outerjoin(Registration, Product.registration_id == Registration.id)
    )
    if query:
        like = f'%{query}%'
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.model.ilike(like),
                Product.specification.ilike(like),
                Product.udi_di.ilike(like),
                Company.name.ilike(like),
            )
        )
    if company:
        stmt = stmt.where(Company.name.ilike(f'%{company}%'))
    if registration_no:
        stmt = stmt.where(Registration.registration_no.ilike(f'%{registration_no}%'))
    return stmt


def search_products(
    db: Session,
    query: str | None,
    company: str | None,
    registration_no: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Product], int]:
    base_stmt = build_search_query(query, company, registration_no)
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    stmt = base_stmt.order_by(Product.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(stmt).unique().all())
    return items, total


def get_product(db: Session, product_id: str) -> Product | None:
    stmt = (
        select(Product)
        .options(joinedload(Product.company), joinedload(Product.registration))
        .where(Product.id == product_id)
    )
    return db.scalar(stmt)


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)
