from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.workers.sync import run_sync_once

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    while True:
        try:
            run_sync_once()
        except Exception as exc:
            logger.error('Sync loop failed: %s', exc)
        time.sleep(settings.sync_interval_seconds)


if __name__ == '__main__':
    main()
