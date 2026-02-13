from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Product, ProductParam, RawDocument


def list_product_params(db: Session, *, product: Product, limit: int = 100) -> list[tuple[ProductParam, RawDocument | None]]:
    stmt = (
        select(ProductParam, RawDocument)
        .outerjoin(RawDocument, RawDocument.id == ProductParam.raw_document_id)
        .where(
            or_(
                ProductParam.di == product.udi_di,
                ProductParam.registry_no == product.reg_no,
            )
        )
        .order_by(ProductParam.param_code.asc(), ProductParam.created_at.desc())
        .limit(max(1, min(int(limit), 500)))
    )
    return list(db.execute(stmt).all())
