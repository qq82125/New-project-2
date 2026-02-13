from __future__ import annotations

from pathlib import Path

import requests


def download_package(url: str, destination: Path, timeout: int = 120) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with destination.open('wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return destination
