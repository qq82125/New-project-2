from __future__ import annotations

import csv
import io
from typing import Any


def parse_nhsa_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode('utf-8', errors='ignore')
    return [dict(r) for r in csv.DictReader(io.StringIO(text))]
