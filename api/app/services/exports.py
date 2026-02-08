from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.products import search_products
from app.repositories.radar import get_export_usage, increase_export_usage


def _plan_limit(plan: str) -> int:
    settings = get_settings()
    mapping = {
        'basic': settings.export_quota_basic_daily,
        'pro': settings.export_quota_pro_daily,
        'enterprise': settings.export_quota_enterprise_daily,
    }
    if plan not in mapping:
        raise HTTPException(status_code=400, detail='Invalid plan')
    return mapping[plan]


def enforce_export_quota(db: Session, plan: str) -> None:
    today = date.today()
    limit = _plan_limit(plan)
    usage = get_export_usage(db, today, plan)
    used = usage.used_count if usage else 0
    if used >= limit:
        raise HTTPException(status_code=429, detail=f'Quota exceeded for plan={plan}, daily limit={limit}')
    increase_export_usage(db, today, plan)


def export_search_to_csv(
    db: Session,
    plan: str,
    q: str | None,
    company: str | None,
    registration_no: str | None,
) -> str:
    enforce_export_quota(db, plan)
    rows, _ = search_products(db, q, company, registration_no, page=1, page_size=5000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['product_id', 'udi_di', 'name', 'model', 'specification', 'category', 'company', 'registration_no'])
    for item in rows:
        writer.writerow(
            [
                str(item.id),
                item.udi_di,
                item.name,
                item.model or '',
                item.specification or '',
                item.category or '',
                item.company.name if item.company else '',
                item.registration.registration_no if item.registration else '',
            ]
        )
    return output.getvalue()
