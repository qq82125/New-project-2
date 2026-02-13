from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Product, SourceRun
from app.services.crawler import fetch_latest_package_meta


def _to_iso(v: datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.isoformat()


def _latest_udi_run(db: Session):
    stmt = (
        select(SourceRun)
        .where(SourceRun.source == 'nmpa_udi')
        .order_by(SourceRun.started_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def run_source_audit(db: Session, settings: Settings) -> dict:
    now = datetime.now(timezone.utc)
    latest_run = _latest_udi_run(db)

    upstream = None
    upstream_err = None
    try:
        meta = fetch_latest_package_meta(settings)
        upstream = {
            'filename': meta.filename,
            'md5': meta.md5,
            'download_url': meta.download_url,
        }
    except Exception as exc:
        upstream_err = str(exc)

    run_info = None
    freshness = {'hours_since_last_run': None, 'is_recent_24h': False}
    package_match = {'same_filename': None, 'same_md5': None}
    if latest_run is not None:
        started_at = getattr(latest_run, 'started_at', None)
        hours = None
        if isinstance(started_at, datetime):
            s0 = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
            hours = (now - s0).total_seconds() / 3600.0
            freshness = {'hours_since_last_run': round(hours, 2), 'is_recent_24h': hours <= 24}
        run_info = {
            'id': int(latest_run.id),
            'status': str(getattr(latest_run, 'status', '') or ''),
            'package_name': getattr(latest_run, 'package_name', None),
            'package_md5': getattr(latest_run, 'package_md5', None),
            'download_url': getattr(latest_run, 'download_url', None),
            'started_at': _to_iso(getattr(latest_run, 'started_at', None)),
            'finished_at': _to_iso(getattr(latest_run, 'finished_at', None)),
        }
        if upstream:
            package_match = {
                'same_filename': (upstream['filename'] == run_info['package_name']),
                'same_md5': (
                    (upstream['md5'] or '').lower() == (run_info['package_md5'] or '').lower()
                    if upstream.get('md5') and run_info.get('package_md5')
                    else None
                ),
            }

    total_products = int(db.scalar(select(func.count(Product.id))) or 0)
    missing_reg_no = int(db.scalar(select(func.count(Product.id)).where((Product.reg_no.is_(None)) | (Product.reg_no == ''))) or 0)
    missing_udi = int(db.scalar(select(func.count(Product.id)).where((Product.udi_di.is_(None)) | (Product.udi_di == ''))) or 0)
    recent_cutoff = now - timedelta(days=1)
    recent_updates = int(db.scalar(select(func.count(Product.id)).where(Product.updated_at >= recent_cutoff)) or 0)

    return {
        'generated_at': now.isoformat(),
        'upstream': upstream,
        'upstream_error': upstream_err,
        'latest_run': run_info,
        'freshness': freshness,
        'package_match': package_match,
        'coverage': {
            'total_products': total_products,
            'missing_reg_no': missing_reg_no,
            'missing_udi_di': missing_udi,
            'updated_last_24h': recent_updates,
        },
        'matching_priority': ['udi_di', 'reg_no', 'company_name+product_name'],
    }

