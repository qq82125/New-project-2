from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import requests
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import DataSource
from app.repositories.radar import get_admin_config
from app.repositories.source_runs import (
    finish_source_run,
    get_running_source_run,
    mark_stale_running_runs_failed,
    start_source_run,
)
from app.services.crypto import decrypt_json
from app.services.crawler import (
    DailyPackage,
    download_file,
    extract_to_staging,
    fetch_latest_package_meta,
    verify_checksum,
)
from app.services.ingest import ingest_staging_records, load_staging_records
from app.services.ivd_classifier import VERSION as IVD_CLASSIFIER_VERSION
from app.services.ivd_dictionary import IVD_SCOPE_ALLOWLIST
from app.services.metrics import generate_daily_metrics
from app.services.subscriptions import dispatch_daily_subscription_digest
from app.pipeline.ingest import save_raw_document_from_path
from app.models import RawDocument
from app.sources.nmpa_udi.parser import parse_udi_zip_bytes
from app.services.udi_variants import upsert_product_variants

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    run_id: int
    status: str
    download_path: str
    staging_path: str
    message: str | None = None


def _pick_primary_source(db) -> DataSource | None:
    try:
        rows = [x for x in db.scalars(select(DataSource).order_by(DataSource.id.asc())).all() if (x.type or '').strip() == 'postgres']
    except Exception:
        return None
    if not rows:
        return None
    # 1) Prefer explicit policy key from admin config.
    try:
        cfg = get_admin_config(db, 'ivd_scope_policy')
        policy = cfg.config_value if cfg and isinstance(cfg.config_value, dict) else {}
        preferred_name = str(policy.get('primary_source') or '').strip()
        if preferred_name:
            for ds in rows:
                if (ds.name or '').strip() == preferred_name:
                    return ds
    except Exception:
        pass
    # 2) Prefer active source.
    active = next((x for x in rows if bool(getattr(x, 'is_active', False))), None)
    if active:
        return active
    # 3) Fallback by name hint.
    return next((x for x in rows if '主数据源' in (x.name or '') or '注册产品库' in (x.name or '')), None)


def _dsn_from_config(cfg: dict) -> URL:
    query = {}
    sslmode = cfg.get('sslmode')
    if sslmode:
        query['sslmode'] = str(sslmode)
    return URL.create(
        'postgresql+psycopg',
        username=str(cfg.get('username') or ''),
        password=str(cfg.get('password') or ''),
        host=str(cfg.get('host') or ''),
        port=int(cfg.get('port') or 5432),
        database=str(cfg.get('database') or ''),
        query=query,
    )


def _sync_from_primary_source(db, run, source: DataSource, *, chunk_size: int = 5000) -> dict:
    def _json_safe(v):
        if isinstance(v, (UUID, datetime, date)):
            return str(v)
        if isinstance(v, dict):
            return {str(k): _json_safe(val) for k, val in v.items()}
        if isinstance(v, list):
            return [_json_safe(x) for x in v]
        return v

    source_cfg = decrypt_json(source.config_encrypted)
    if not isinstance(source_cfg, dict):
        raise RuntimeError('primary source config invalid')
    source_query = str(source_cfg.get('source_query') or '').strip()
    source_table = str(source_cfg.get('source_table') or '').strip() or 'public.products'
    sql = source_query or f"select * from {source_table}"
    engine = create_engine(_dsn_from_config(source_cfg), pool_pre_ping=True, poolclass=NullPool)
    total_scanned = 0
    total_success = 0
    total_failed = 0
    total_filtered = 0
    total_added = 0
    total_updated = 0
    total_removed = 0
    try:
        with engine.connect() as conn:
            rows = conn.execution_options(stream_results=True).execute(
                text(sql)
            ).mappings()
            batch: list[dict] = []
            for row in rows:
                batch.append({str(k): _json_safe(v) for k, v in dict(row).items()})
                if len(batch) >= chunk_size:
                    s = ingest_staging_records(db, batch, run.id, source=str(getattr(run, 'source', '') or run_source_name or 'nmpa_source'))
                    total_scanned += int(s.get('total', 0) or 0)
                    total_success += int(s.get('success', 0) or 0)
                    total_failed += int(s.get('failed', 0) or 0)
                    total_filtered += int(s.get('filtered', 0) or 0)
                    total_added += int(s.get('added', 0) or 0)
                    total_updated += int(s.get('updated', 0) or 0)
                    total_removed += int(s.get('removed', 0) or 0)
                    batch = []
            if batch:
                s = ingest_staging_records(db, batch, run.id, source=str(getattr(run, 'source', '') or run_source_name or 'nmpa_source'))
                total_scanned += int(s.get('total', 0) or 0)
                total_success += int(s.get('success', 0) or 0)
                total_failed += int(s.get('failed', 0) or 0)
                total_filtered += int(s.get('filtered', 0) or 0)
                total_added += int(s.get('added', 0) or 0)
                total_updated += int(s.get('updated', 0) or 0)
                total_removed += int(s.get('removed', 0) or 0)
    finally:
        engine.dispose()
    return {
        'total': total_scanned,
        'success': total_success,
        'failed': total_failed,
        'filtered': total_filtered,
        'added': total_added,
        'updated': total_updated,
        'removed': total_removed,
        'source_table': source_table,
        'source_query_used': bool(source_query),
    }


def prepare_staging_dirs(staging_root: Path, run_id: int, clean: bool = True) -> tuple[Path, Path]:
    # Use per-run isolated workspace to avoid cross-run cleanup races.
    run_root = staging_root / f'run_{int(run_id)}'
    if clean and run_root.exists():
        shutil.rmtree(run_root, ignore_errors=True)
    download_dir = run_root / 'downloads'
    extract_dir = run_root / 'extracted'
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

    db = SessionLocal()
    primary_source = _pick_primary_source(db)
    run_source_name = 'nmpa_registry' if primary_source else 'nmpa_udi'
    stale_minutes = max(5, int(getattr(settings, 'sync_stale_run_minutes', 30) or 30))
    mark_stale_running_runs_failed(db, source=run_source_name, stale_after_minutes=stale_minutes)
    running = get_running_source_run(db, run_source_name)
    if running is not None:
        db.close()
        return SyncResult(
            run_id=int(running.id),
            status='skipped',
            download_path='',
            staging_path='',
            message=f'skipped: existing RUNNING run #{running.id}',
        )
    run = start_source_run(
        db,
        source=run_source_name,
        package_name=None,
        package_md5=checksum if checksum_algorithm == 'md5' else None,
        download_url=package_url,
    )
    download_dir, extract_dir = prepare_staging_dirs(staging_root, run_id=run.id, clean=clean_staging)

    try:
        if primary_source is not None:
            stats = _sync_from_primary_source(db, run, primary_source)
            finish_source_run(
                db,
                run,
                status='success',
                message=f'primary source synced: {primary_source.name}',
                records_total=stats['total'],
                records_success=stats['success'],
                records_failed=stats['failed'],
                added_count=stats['added'],
                updated_count=stats['updated'],
                removed_count=stats['removed'],
                ivd_kept_count=stats['success'],
                non_ivd_skipped_count=stats['filtered'],
                source_notes={
                    'mode': 'primary_source',
                    'primary_source_id': int(primary_source.id),
                    'primary_source_name': primary_source.name,
                    'source_table': stats.get('source_table'),
                    'source_query_used': bool(stats.get('source_query_used')),
                    'ivd_classifier_version': int(IVD_CLASSIFIER_VERSION),
                    'ivd_scope_allowlist': list(IVD_SCOPE_ALLOWLIST),
                },
            )
            generate_daily_metrics(db)
            dispatch_daily_subscription_digest(db)
            return SyncResult(
                run_id=run.id,
                status='success',
                download_path='',
                staging_path=str(extract_dir),
                message=f'primary source synced: {primary_source.name}',
            )

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

        raw_doc_id = save_raw_document_from_path(
            db,
            source='NMPA_UDI',
            url=package.download_url,
            file_path=archive_path,
            doc_type='archive',
            run_id=f'source_run:{int(run.id)}',
        )
        # Parse/extract should read from raw storage to ensure the evidence chain is authoritative.
        raw_archive_path = archive_path
        try:
            doc = db.get(RawDocument, raw_doc_id)
            if doc is not None and doc.storage_uri:
                raw_archive_path = Path(str(doc.storage_uri))
        except Exception:
            raw_archive_path = archive_path

        # Best-effort: parse DI-level variants for packaging/manufacturer enrichment.
        variant_report = None
        try:
            variant_rows = parse_udi_zip_bytes(raw_archive_path.read_bytes())
            variant_result = upsert_product_variants(
                db,
                rows=variant_rows,
                raw_document_id=raw_doc_id,
                source_run_id=int(run.id),
                dry_run=False,
            )
            variant_report = {
                'total': variant_result.total,
                'skipped': variant_result.skipped,
                'upserted': variant_result.upserted,
                'ivd_true': variant_result.ivd_true,
                'ivd_false': variant_result.ivd_false,
                'linked_products': variant_result.linked_products,
            }
        except Exception as exc:
            variant_report = {'error': str(exc)}

        extract_to_staging(raw_archive_path, extract_dir)
        records = load_staging_records(extract_dir)
        try:
            stats = ingest_staging_records(db, records, run.id, source='NMPA_UDI', raw_document_id=raw_doc_id)
        except TypeError:
            # Backward-compat for older stubs/mocks that don't accept raw_document_id.
            stats = ingest_staging_records(db, records, run.id)

        # Update evidence chain parse status for this package.
        try:
            doc = db.get(RawDocument, raw_doc_id)
            if doc is not None:
                doc.parse_status = 'PARSED'
                doc.parse_log = {
                    'kind': 'nmpa_udi_package',
                    'source_run_id': int(run.id),
                    'package_name': package.filename,
                    'checksum_algorithm': checksum_algorithm,
                    'md5': (checksum or package.md5),
                    'ingest_stats': dict(stats),
                    'variant_report': variant_report,
                }
                db.add(doc)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

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
            ivd_kept_count=stats['success'],
            non_ivd_skipped_count=stats['filtered'],
            source_notes={
                'ingest_filtered_non_ivd': int(stats['filtered']),
                'raw_document_id': str(raw_doc_id),
                'ivd_classifier_version': int(IVD_CLASSIFIER_VERSION),
                'ivd_scope_allowlist': list(IVD_SCOPE_ALLOWLIST),
                'variant_report': variant_report,
            },
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
        try:
            db.rollback()
        except Exception:
            pass
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
