from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def list_recent_announcements(days: int = 7) -> list[dict[str, Any]]:
    """Placeholder low-frequency adapter.

    The project intentionally avoids aggressive crawling/anti-bot bypassing.
    """
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    return [
        {
            'title': '示例公告',
            'published_at': cutoff.isoformat() + 'Z',
            'attachment_url': None,
        }
    ]
