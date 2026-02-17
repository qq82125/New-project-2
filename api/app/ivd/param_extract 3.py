from __future__ import annotations

import re
from typing import Any

from app.ivd.ontology import PARAM_ONTOLOGY

_NUM_UNIT_PAT = re.compile(r'(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z%/]+)')


def extract_from_text(text: str, ontology: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    ont = ontology or PARAM_ONTOLOGY
    t = str(text or '')
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    out: list[dict[str, Any]] = []
    for line in lines:
        lower = line.lower()
        for code, meta in ont.items():
            aliases = [str(x).lower() for x in (meta.get('aliases') or [])]
            if not any(alias in lower for alias in aliases):
                continue
            m = _NUM_UNIT_PAT.search(line)
            out.append(
                {
                    'param_code': code,
                    'value_num': (float(m.group('num')) if m else None),
                    'value_text': line if not m else None,
                    'unit': (m.group('unit') if m else None),
                    'evidence_text': line[:500],
                    'confidence': 0.70,
                }
            )
    return out


def normalize_units(unit: str | None) -> str | None:
    if unit is None:
        return None
    m = unit.strip()
    if not m:
        return None
    if m.lower() in {'hours', 'hour', 'hrs'}:
        return 'h'
    if m.lower() in {'minutes', 'minute', 'mins'}:
        return 'min'
    return m
