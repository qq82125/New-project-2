from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import time
from typing import Any

from app.db.session import SessionLocal
from app.repositories.radar import get_admin_config, upsert_admin_config
from app.core.config import get_settings
from app.services.signals_v1 import DEFAULT_WINDOW, compute_signals_v1
from app.services.supplement_sync import (
    DEFAULT_SUPPLEMENT_SOURCE_NAME,
    run_nmpa_query_supplement_now,
    run_supplement_sync_now,
    should_run_nmpa_query_supplement,
    should_run_supplement,
)
from app.workers.sync import sync_nmpa_ivd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


SIGNALS_DAILY_KEY = 'signals_compute_daily_last_run'


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _signals_last_success_as_of(db) -> date | None:
    cfg = get_admin_config(db, SIGNALS_DAILY_KEY)
    if not cfg or not isinstance(cfg.config_value, dict):
        return None
    raw = cfg.config_value.get('as_of_date')
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except Exception:
        return None


def _run_signals_compute_daily_job() -> None:
    db = SessionLocal()
    try:
        today = _today_utc()
        last_success = _signals_last_success_as_of(db)
        if last_success == today:
            logger.info('Job signals_compute_daily skipped: already_successful_as_of=%s', today.isoformat())
            return

        started = datetime.now(timezone.utc)
        logger.info('Job signals_compute_daily started: as_of_date=%s window=%s', today.isoformat(), DEFAULT_WINDOW)
        result = compute_signals_v1(
            db,
            as_of=today,
            window=DEFAULT_WINDOW,
            dry_run=False,
        )
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        report: dict[str, Any] = {
            'job': 'signals_compute_daily',
            'status': ('success' if result.ok else 'failed'),
            'as_of_date': today.isoformat(),
            'window': DEFAULT_WINDOW,
            'started_at': _to_iso(started),
            'finished_at': _to_iso(datetime.now(timezone.utc)),
            'duration_seconds': round(elapsed_s, 3),
            'registration_count': int(result.registration_count),
            'track_count': int(result.track_count),
            'company_count': int(result.company_count),
            'wrote_total': int(result.wrote_total),
            'error': result.error,
        }
        upsert_admin_config(db, SIGNALS_DAILY_KEY, report)
        logger.info(
            'Job signals_compute_daily finished: as_of_date=%s wrote_total=%s registration=%s track=%s company=%s duration_s=%.3f',
            today.isoformat(),
            result.wrote_total,
            result.registration_count,
            result.track_count,
            result.company_count,
            elapsed_s,
        )
    except Exception as exc:
        logger.exception('Job signals_compute_daily failed: %s', exc)
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    _bootstrap_schedule = {
        'enabled': bool(getattr(settings, 'supplement_sync_enabled', False)),
        'interval_hours': max(1, int(getattr(settings, 'supplement_sync_interval_hours', 24) or 24)),
        'batch_size': max(50, int(getattr(settings, 'supplement_sync_batch_size', 1000) or 1000)),
        'recent_hours': max(1, int(getattr(settings, 'supplement_sync_recent_hours', 72) or 72)),
        'source_name': DEFAULT_SUPPLEMENT_SOURCE_NAME,
        'nmpa_query_enabled': True,
        'nmpa_query_interval_hours': 24,
        'nmpa_query_batch_size': 200,
        'nmpa_query_url': 'https://www.nmpa.gov.cn/datasearch/home-index.html?itemId=2c9ba384759c957701759ccef50f032b#category=ylqx',
        'nmpa_query_timeout_seconds': 20,
    }
    db0 = SessionLocal()
    try:
        exists = get_admin_config(db0, 'source_supplement_schedule')
        if not exists or not isinstance(exists.config_value, dict):
            upsert_admin_config(db0, 'source_supplement_schedule', _bootstrap_schedule)
    finally:
        db0.close()

    last_failure: str | None = None
    repeated_failures = 0
    while True:
        result = sync_nmpa_ivd()
        if result.status == 'skipped':
            logger.info(result.message or 'Sync skipped')
        elif result.status != 'success':
            message = result.message or 'unknown error'
            if message == last_failure:
                repeated_failures += 1
            else:
                last_failure = message
                repeated_failures = 1

            if repeated_failures == 1 or repeated_failures % 10 == 0:
                logger.error('Sync failed (%s): %s', repeated_failures, message)
        elif last_failure is not None:
            logger.info('Sync recovered after %s failures', repeated_failures)
            last_failure = None
            repeated_failures = 0

        def _job_supplement_sync() -> None:
            db = SessionLocal()
            try:
                should_run, _, reason = should_run_supplement(db)
                if should_run:
                    supplement_report = run_supplement_sync_now(db, reason=f'auto:{reason}')
                    logger.info(
                        'Supplement sync finished: status=%s scanned=%s updated=%s',
                        supplement_report.get('status'),
                        supplement_report.get('scanned'),
                        supplement_report.get('updated'),
                    )
            finally:
                db.close()

        def _job_nmpa_query_supplement() -> None:
            db = SessionLocal()
            try:
                should_run_q, _, reason_q = should_run_nmpa_query_supplement(db)
                if should_run_q:
                    query_report = run_nmpa_query_supplement_now(db, reason=f'auto:{reason_q}')
                    logger.info(
                        'NMPA-query supplement finished: status=%s scanned=%s updated=%s blocked_412=%s',
                        query_report.get('status'),
                        query_report.get('scanned'),
                        query_report.get('updated'),
                        query_report.get('blocked_412'),
                    )
            finally:
                db.close()

        jobs: list[tuple[str, Any]] = [
            ('supplement_sync', _job_supplement_sync),
            ('nmpa_query_supplement', _job_nmpa_query_supplement),
            ('signals_compute_daily', _run_signals_compute_daily_job),
        ]
        for job_name, job_fn in jobs:
            try:
                job_fn()
            except Exception as exc:
                logger.error('Loop job %s failed: %s', job_name, exc)
        time.sleep(settings.sync_interval_seconds)


if __name__ == '__main__':
    main()
