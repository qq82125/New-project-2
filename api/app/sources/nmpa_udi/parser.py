from __future__ import annotations

import csv
import io
import zipfile
from typing import Any


def parse_udi_zip_bytes(content: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in z.namelist():
            if not name.lower().endswith('.csv'):
                continue
            with z.open(name) as fp:
                text = fp.read().decode('utf-8', errors='ignore')
                reader = csv.DictReader(io.StringIO(text))
                out.extend([dict(r) for r in reader])
    return out
