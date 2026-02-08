from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.workers.sync import sync_nmpa_ivd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    last_failure: str | None = None
    repeated_failures = 0
    while True:
        result = sync_nmpa_ivd()
        if result.status != 'success':
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
        time.sleep(settings.sync_interval_seconds)


if __name__ == '__main__':
    main()
