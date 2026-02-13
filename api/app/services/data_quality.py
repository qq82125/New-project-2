from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Product

_PLACEHOLDER_NAMES = {'na', 'n/a', 'null', 'none', 'unknown', 'test', 'demo', '-', '--', '/', '_'}
_PLACEHOLDER_REG_NO = {'', '-', '--', '/', 'n/a', 'na', 'null', 'none', 'unknown'}


def _is_blank(text: str | None) -> bool:
    return not bool((text or '').strip())


def _is_punct_only(text: str | None) -> bool:
    s = (text or '').strip()
    if not s:
        return False
    return not any(ch.isalnum() or ('\u4e00' <= ch <= '\u9fff') for ch in s)


def _is_placeholder_name(text: str | None) -> bool:
    s = (text or '').strip().lower()
    return s in _PLACEHOLDER_NAMES


def _is_placeholder_reg_no(text: str | None) -> bool:
    s = (text or '').strip().lower()
    return s in _PLACEHOLDER_REG_NO


def _sample_row(p: Product) -> dict:
    return {
        'id': str(p.id),
        'name': p.name,
        'udi_di': p.udi_di,
        'reg_no': p.reg_no,
        'class_name': p.class_name,
        'ivd_category': p.ivd_category,
        'updated_at': (p.updated_at.isoformat() if getattr(p, 'updated_at', None) else None),
    }


def run_data_quality_audit(db: Session, *, sample_limit: int = 20) -> dict:
    now = datetime.now(timezone.utc)
    safe_limit = max(1, min(int(sample_limit), 100))

    total_ivd = int(db.scalar(select(func.count(Product.id)).where(Product.is_ivd.is_(True))) or 0)

    ivd_rows = list(
        db.scalars(
            select(Product).where(Product.is_ivd.is_(True)).order_by(Product.updated_at.desc()).limit(5000)
        ).all()
    )

    bad_name_blank = [p for p in ivd_rows if _is_blank(getattr(p, 'name', None))]
    bad_name_punct = [p for p in ivd_rows if _is_punct_only(getattr(p, 'name', None))]
    bad_name_placeholder = [p for p in ivd_rows if _is_placeholder_name(getattr(p, 'name', None))]
    bad_name_short = [p for p in ivd_rows if len((getattr(p, 'name', '') or '').strip()) <= 1 and not _is_blank(getattr(p, 'name', None))]
    bad_reg_placeholder = [p for p in ivd_rows if _is_placeholder_reg_no(getattr(p, 'reg_no', None))]
    bad_class_missing = [p for p in ivd_rows if _is_blank(getattr(p, 'class_name', None))]
    company_ids = {p.company_id for p in ivd_rows if getattr(p, 'company_id', None) is not None}
    existing_company_ids = set(
        db.scalars(select(Company.id).where(Company.id.in_(company_ids))).all()
    ) if company_ids else set()
    bad_company_missing = [
        p
        for p in ivd_rows
        if getattr(p, 'company_id', None) is None or p.company_id not in existing_company_ids
    ]

    samples = {
        'name_blank': [_sample_row(p) for p in bad_name_blank[:safe_limit]],
        'name_punct_only': [_sample_row(p) for p in bad_name_punct[:safe_limit]],
        'name_placeholder': [_sample_row(p) for p in bad_name_placeholder[:safe_limit]],
        'name_too_short': [_sample_row(p) for p in bad_name_short[:safe_limit]],
        'reg_no_placeholder': [_sample_row(p) for p in bad_reg_placeholder[:safe_limit]],
        'class_missing': [_sample_row(p) for p in bad_class_missing[:safe_limit]],
        'company_missing': [_sample_row(p) for p in bad_company_missing[:safe_limit]],
    }

    counters = {
        'total_ivd': total_ivd,
        'name_blank': len(bad_name_blank),
        'name_punct_only': len(bad_name_punct),
        'name_placeholder': len(bad_name_placeholder),
        'name_too_short': len(bad_name_short),
        'reg_no_placeholder': len(bad_reg_placeholder),
        'class_missing': len(bad_class_missing),
        'company_missing': len(bad_company_missing),
    }

    return {
        'generated_at': now.isoformat(),
        'sample_limit': safe_limit,
        'counters': counters,
        'samples': samples,
    }
