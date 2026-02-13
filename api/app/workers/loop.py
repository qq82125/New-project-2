from __future__ import annotations

import logging
import time

from app.db.session import SessionLocal
from app.repositories.radar import get_admin_config, upsert_admin_config
from app.core.config import get_settings
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
        except Exception as exc:
            logger.error('Supplement sync check failed: %s', exc)
        finally:
            db.close()
        time.sleep(settings.sync_interval_seconds)


if __name__ == '__main__':
    main()
