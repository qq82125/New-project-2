from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.ivd.classifier import DEFAULT_VERSION as IVD_CLASSIFIER_VERSION, classify
from app.services.ivd_classifier import VERSION as INTERNAL_RULE_VERSION


@dataclass
class ReclassifyResult:
    dry_run: bool
    scanned: int
    would_update: int
    updated: int
    ivd_true: int
    ivd_false: int
    ivd_version: int


def _extract_class_code_from_values(raw_json: Any, class_name: Any) -> str:
    raw = raw_json if isinstance(raw_json, dict) else {}
    for key in ('classification_code', 'class_code', 'flbm', 'cplb', '管理类别', '类别', 'class', 'class_name'):
        v = raw.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return str(class_name or '').strip()


def _normalize_result(decision: dict[str, Any]) -> tuple[bool, str | None, list[str], dict[str, Any] | None, int]:
    is_ivd = bool(decision.get('is_ivd'))
    ivd_category = str(decision.get('ivd_category')) if decision.get('ivd_category') is not None else None
    ivd_subtypes = [str(x) for x in (decision.get('ivd_subtypes') or []) if str(x).strip()]
    reason = decision.get('reason') if isinstance(decision.get('reason'), dict) else None
    version = int(decision.get('rule_version') or 1)
    return is_ivd, ivd_category, ivd_subtypes, reason, version


def run_reclassify_ivd(db: Session, *, dry_run: bool) -> ReclassifyResult:
    scanned = 0
    would_update = 0
    updated = 0
    ivd_true = 0
    ivd_false = 0
    update_batch: list[dict[str, Any]] = []
    batch_size = 1000
    last_id = None

    while True:
        stmt = select(
            Product.id,
            Product.name,
            Product.class_name,
            Product.raw_json,
            Product.is_ivd,
            Product.ivd_category,
            Product.ivd_subtypes,
            Product.ivd_reason,
            Product.ivd_version,
        ).order_by(Product.id.asc()).limit(batch_size)
        if last_id is not None:
            stmt = stmt.where(Product.id > last_id)
        rows = list(db.execute(stmt).all())
        if not rows:
            break

        for p in rows:
            scanned += 1
            decision = classify(
                {
                    'name': str(getattr(p, 'name', '') or ''),
                    'classification_code': _extract_class_code_from_values(getattr(p, 'raw_json', None), getattr(p, 'class_name', None)),
                },
                version=IVD_CLASSIFIER_VERSION,
            )
            is_ivd, ivd_category, ivd_subtypes, reason, version = _normalize_result(decision)
            if is_ivd:
                ivd_true += 1
            else:
                ivd_false += 1

            changed = (
                getattr(p, 'is_ivd', None) is not is_ivd
                or getattr(p, 'ivd_category', None) != ivd_category
                or (getattr(p, 'ivd_subtypes', None) or []) != ivd_subtypes
                or getattr(p, 'ivd_reason', None) != reason
                or int(getattr(p, 'ivd_version', 1) or 1) != version
            )
            if not changed:
                continue
            would_update += 1
            if dry_run:
                continue
            update_batch.append(
                {
                    'id': p.id,
                    'is_ivd': is_ivd,
                    'ivd_category': ivd_category,
                    'ivd_subtypes': ivd_subtypes,
                    'ivd_reason': reason,
                    'ivd_version': version,
                }
            )
            updated += 1

        if not dry_run and update_batch:
            db.bulk_update_mappings(Product, update_batch)
            db.commit()
            update_batch = []
        last_id = rows[-1].id

    if not dry_run and update_batch:
        db.bulk_update_mappings(Product, update_batch)
        db.commit()

    return ReclassifyResult(
        dry_run=bool(dry_run),
        scanned=scanned,
        would_update=would_update,
        updated=updated,
        ivd_true=ivd_true,
        ivd_false=ivd_false,
        ivd_version=int(INTERNAL_RULE_VERSION),
    )
