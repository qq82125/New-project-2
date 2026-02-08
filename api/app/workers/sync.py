from __future__ import annotations

import logging
from pathlib import Path

import requests

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.source_runs import finish_source_run, start_source_run
from app.services.crawler import (
    download_file,
    extract_to_staging,
    fetch_latest_package_meta,
    verify_md5,
)
from app.services.ingest import ingest_staging_records, load_staging_records

logger = logging.getLogger(__name__)


def send_webhook(webhook_url: str | None, payload: dict) -> None:
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as exc:
        logger.error('Failed to send webhook: %s', exc)


def run_sync_once() -> None:
    settings = get_settings()
    staging_root = Path(settings.staging_dir)
    download_dir = staging_root / 'downloads'
    extract_dir = staging_root / 'extracted'

    db = SessionLocal()
    run = None
    try:
        package = fetch_latest_package_meta(settings)
        run = start_source_run(
            db,
            source='nmpa_udi',
            package_name=package.filename,
            package_md5=package.md5,
            download_url=package.download_url,
        )

        archive_path = download_file(package.download_url, download_dir / package.filename)
        if not verify_md5(archive_path, package.md5):
            raise ValueError(f'MD5 mismatch for {archive_path.name}')

        extract_to_staging(archive_path, extract_dir)
        records = load_staging_records(extract_dir)
        total, success, failed = ingest_staging_records(db, records, run.id)

        finish_source_run(
            db,
            run,
            status='SUCCESS' if failed == 0 else 'PARTIAL_SUCCESS',
            message=None if failed == 0 else f'Failed records: {failed}',
            records_total=total,
            records_success=success,
            records_failed=failed,
        )
    except Exception as exc:
        logger.exception('Sync failed')
        if run is not None:
            finish_source_run(
                db,
                run,
                status='FAILED',
                message=str(exc),
                records_total=0,
                records_success=0,
                records_failed=0,
            )
        send_webhook(settings.webhook_url, {'status': 'FAILED', 'error': str(exc)})
        raise
    finally:
        db.close()
