from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.source_runs import finish_source_run, start_source_run
from app.services.crawler import (
    DailyPackage,
    download_file,
    extract_to_staging,
    fetch_latest_package_meta,
    verify_checksum,
)
from app.services.ingest import ingest_staging_records, load_staging_records
from app.services.metrics import generate_daily_metrics
from app.services.subscriptions import dispatch_daily_subscription_digest

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    run_id: int
    status: str
    download_path: str
    staging_path: str
    message: str | None = None


def prepare_staging_dirs(staging_root: Path, clean: bool = True) -> tuple[Path, Path]:
    if clean and staging_root.exists():
        # Do not remove the mount root itself (e.g. /app/staging volume).
        for child in staging_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=False)
            else:
                child.unlink(missing_ok=True)
    download_dir = staging_root / 'downloads'
    extract_dir = staging_root / 'extracted'
    download_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    return download_dir, extract_dir


def _package_from_url(url: str, checksum: str | None = None) -> DailyPackage:
    filename = Path(urlparse(url).path).name or 'package.bin'
    return DailyPackage(filename=filename, md5=checksum, download_url=url)


def _run_with_retries(func, *, attempts: int, base_backoff: int, multiplier: float, operation: str):
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            sleep_seconds = base_backoff * (multiplier ** (attempt - 1))
            logger.warning(
                '%s failed (attempt %s/%s): %s; retrying in %.1fs',
                operation,
                attempt,
                attempts,
                exc,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f'{operation} failed with unknown error')


def sync_nmpa_ivd(
    *,
    package_url: str | None = None,
    checksum: str | None = None,
    checksum_algorithm: str = 'md5',
    clean_staging: bool = True,
) -> SyncResult:
    settings = get_settings()
    retry_attempts = max(1, int(getattr(settings, 'sync_retry_attempts', 3)))
    retry_backoff = max(1, int(getattr(settings, 'sync_retry_backoff_seconds', 5)))
    retry_multiplier = max(1.0, float(getattr(settings, 'sync_retry_backoff_multiplier', 2.0)))
    staging_root = Path(settings.staging_dir)
    download_dir, extract_dir = prepare_staging_dirs(staging_root, clean=clean_staging)

    db = SessionLocal()
    run = start_source_run(
        db,
        source='nmpa_udi',
        package_name=None,
        package_md5=checksum if checksum_algorithm == 'md5' else None,
        download_url=package_url,
    )

    try:
        package = (
            _package_from_url(package_url, checksum)
            if package_url
            else _run_with_retries(
                lambda: fetch_latest_package_meta(settings),
                attempts=retry_attempts,
                base_backoff=retry_backoff,
                multiplier=retry_multiplier,
                operation='fetch_latest_package_meta',
            )
        )
        run.package_name = package.filename
        run.package_md5 = package.md5 if checksum_algorithm == 'md5' else None
        run.download_url = package.download_url
        db.add(run)
        db.commit()

        archive_path = _run_with_retries(
            lambda: download_file(package.download_url, download_dir / package.filename),
            attempts=retry_attempts,
            base_backoff=retry_backoff,
            multiplier=retry_multiplier,
            operation='download_file',
        )
        if not verify_checksum(archive_path, checksum or package.md5, algorithm=checksum_algorithm):
            raise ValueError(f'{checksum_algorithm.upper()} mismatch for {archive_path.name}')

        extract_to_staging(archive_path, extract_dir)
        records = load_staging_records(extract_dir)
        stats = ingest_staging_records(db, records, run.id)
        finish_source_run(
            db,
            run,
            status='success',
            message='downloaded, extracted and ingested',
            records_total=stats['total'],
            records_success=stats['success'],
            records_failed=stats['failed'],
            added_count=stats['added'],
            updated_count=stats['updated'],
            removed_count=stats['removed'],
        )
        generate_daily_metrics(db)
        dispatch_daily_subscription_digest(db)
        return SyncResult(
            run_id=run.id,
            status='success',
            download_path=str(archive_path),
            staging_path=str(extract_dir),
            message='downloaded, extracted and ingested',
        )
    except Exception as exc:
        logger.exception('sync_nmpa_ivd failed')
        finish_source_run(
            db,
            run,
            status='failed',
            message=str(exc),
            records_total=0,
            records_success=0,
            records_failed=0,
        )
        return SyncResult(
            run_id=run.id,
            status='failed',
            download_path='',
            staging_path=str(extract_dir),
            message=str(exc),
        )
    finally:
        db.close()


def run_sync_once() -> None:
    result = sync_nmpa_ivd()
    if result.status != 'success':
        raise RuntimeError(result.message or 'sync_nmpa_ivd failed')
