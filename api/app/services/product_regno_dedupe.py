from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product


@dataclass
class ProductRegnoDedupeReport:
    dry_run: bool
    limit_regnos: int | None
    dup_regno_count: int = 0
    affected_products_count: int = 0
    canonical_count: int = 0
    hidden_count: int = 0
    sample: list[dict[str, Any]] = field(default_factory=list)
    processed_regnos: list[str] = field(default_factory=list)

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": bool(self.dry_run),
            "limit_regnos": self.limit_regnos,
            "dup_regno_count": int(self.dup_regno_count),
            "affected_products_count": int(self.affected_products_count),
            "canonical_count": int(self.canonical_count),
            "hidden_count": int(self.hidden_count),
            "sample": list(self.sample),
            "processed_regnos": list(self.processed_regnos),
        }


def _stub_verified_flags(product: Product) -> tuple[bool, bool]:
    raw = getattr(product, "raw_json", None) or {}
    if not isinstance(raw, dict):
        return False, False
    stub = raw.get("_stub")
    if not isinstance(stub, dict):
        return False, False

    is_stub = bool(stub.get("is_stub"))
    verified = bool(stub.get("verified_by_nmpa"))

    # Backward compatibility with earlier stub shape.
    if not is_stub and (str(stub.get("source_hint") or "").strip().upper() == "UDI") and not verified:
        is_stub = True
    return is_stub, verified


def _sort_key(product: Product) -> tuple[int, int, float, str]:
    is_stub, verified = _stub_verified_flags(product)
    updated_at = getattr(product, "updated_at", None)
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_ts = updated_at.replace(tzinfo=timezone.utc).timestamp()
        else:
            updated_ts = updated_at.timestamp()
    else:
        updated_ts = 0.0
    # Lower tuple is preferred.
    return (1 if is_stub else 0, 0 if verified else 1, -updated_ts, str(product.id))


def _choose_canonical(items: list[Product]) -> Product:
    return sorted(items, key=_sort_key)[0]


def dedupe_products_by_reg_no(
    db: Session,
    *,
    dry_run: bool = True,
    limit_regnos: int | None = None,
) -> ProductRegnoDedupeReport:
    report = ProductRegnoDedupeReport(dry_run=dry_run, limit_regnos=limit_regnos)

    dup_stmt = (
        select(Product.reg_no, func.count(Product.id).label("cnt"))
        .where(Product.reg_no.is_not(None), Product.reg_no != "")
        .group_by(Product.reg_no)
        .having(func.count(Product.id) > 1)
        .order_by(func.count(Product.id).desc(), Product.reg_no.asc())
    )
    if limit_regnos is not None and limit_regnos > 0:
        dup_stmt = dup_stmt.limit(limit_regnos)
    dup_rows = list(db.execute(dup_stmt).all())
    report.dup_regno_count = len(dup_rows)

    for reg_no, count in dup_rows:
        rows = list(
            db.scalars(
                select(Product).where(Product.reg_no == reg_no).order_by(Product.updated_at.desc(), Product.id.asc())
            ).all()
        )
        if len(rows) <= 1:
            continue

        canonical = _choose_canonical(rows)
        report.processed_regnos.append(str(reg_no))
        report.affected_products_count += len(rows)
        report.canonical_count += 1
        report.hidden_count += max(0, len(rows) - 1)

        if len(report.sample) < 10:
            report.sample.append(
                {
                    "reg_no": str(reg_no),
                    "count": int(count),
                    "canonical_product_id": str(canonical.id),
                    "hidden_product_ids": [str(item.id) for item in rows if item.id != canonical.id],
                }
            )

        if dry_run:
            continue

        # canonical should always stay visible
        canonical.is_hidden = False
        canonical.superseded_by = None
        for item in rows:
            if item.id == canonical.id:
                continue
            item.is_hidden = True
            item.superseded_by = canonical.id

    return report
