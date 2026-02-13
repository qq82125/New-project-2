from __future__ import annotations

import requests


def fetch_monthly_snapshot(url: str, *, timeout: int = 30) -> bytes:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content
