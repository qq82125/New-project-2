from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductParam
from app.ivd.param_extract import extract_from_text, normalize_units


def normalize_params_to_db(
    db: Session,
    *,
    raw_document_id: UUID,
    text: str,
    di: str | None = None,
    registry_no: str | None = None,
    extract_version: str = 'param_v1_20260213',
    evidence_page: int | None = None,
) -> int:
    items = extract_from_text(text)
    written = 0
    for item in items:
        row = ProductParam(
            di=di,
            registry_no=registry_no,
            param_code=str(item.get('param_code')),
            value_num=item.get('value_num'),
            value_text=item.get('value_text'),
            unit=normalize_units(item.get('unit')),
            conditions={},
            evidence_text=str(item.get('evidence_text') or '')[:2000],
            evidence_page=evidence_page,
            raw_document_id=raw_document_id,
            confidence=float(item.get('confidence', 0.5)),
            extract_version=extract_version,
        )
        db.add(row)
        written += 1
    db.commit()
    return written


def bind_product_for_document(db: Session, *, di: str | None, registry_no: str | None) -> Product | None:
    if di:
        p = db.scalar(select(Product).where(Product.udi_di == di, Product.is_ivd.is_(True)).limit(1))
        if p is not None:
            return p
    if registry_no:
        return db.scalar(select(Product).where(Product.reg_no == registry_no, Product.is_ivd.is_(True)).limit(1))
    return None
