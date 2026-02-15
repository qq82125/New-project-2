from __future__ import annotations

import re
from typing import Any

from app.ivd.ontology import PARAM_ONTOLOGY


# Basic numeric patterns
_NUM = r"(?P<num>\d+(?:\.\d+)?)"
_RANGE = r"(?P<low>\d+(?:\.\d+)?)\s*(?:-|~|－|—|至|到)\s*(?P<high>\d+(?:\.\d+)?)"

# Units: keep permissive; normalize later.
_UNIT = r"(?P<unit>[a-zA-Zμµ°℃/%]+(?:/[a-zA-Zμµ°℃%]+)?)"

_RANGE_UNIT_PAT = re.compile(_RANGE + r"\s*" + _UNIT)
_NUM_UNIT_PAT = re.compile(_NUM + r"\s*" + _UNIT)
_PCT_PAT = re.compile(_NUM + r"\s*%")
_TEMP_RANGE_PAT = re.compile(_RANGE + r"\s*(?:°C|℃|C)")
_TEMP_SINGLE_PAT = re.compile(_NUM + r"\s*(?:°C|℃|C)")


def _contains_any(haystack_lower: str, aliases: list[str]) -> bool:
    return any(a and a in haystack_lower for a in aliases)


def normalize_units(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = str(unit).strip()
    if not u:
        return None
    u0 = u.replace("μ", "u").replace("µ", "u")
    low = u0.lower()
    if low in {"hours", "hour", "hrs", "hr", "小时", "时"}:
        return "h"
    if low in {"minutes", "minute", "mins", "min", "分钟", "分"}:
        return "min"
    if low in {"days", "day", "天"}:
        return "day"
    if low in {"months", "month", "月"}:
        return "month"
    if low in {"years", "year", "年"}:
        return "year"
    if low in {"°c", "℃", "c", "摄氏度"}:
        return "C"
    if low in {"ml"}:
        return "mL"
    if low in {"ul"}:
        return "uL"
    if low in {"iu/ml"}:
        return "IU/mL"
    if low in {"copies/ml"}:
        return "copies/mL"
    if low in {"ng/ml"}:
        return "ng/mL"
    return u0


def _extract_value(line: str) -> dict[str, Any]:
    """Extract one best-effort value from a line.

    Supports:
    - ranges like 1-5 ng/mL
    - percentages like 95%
    - numeric+unit
    - temperature range/single (for storage conditions)
    """
    m = _RANGE_UNIT_PAT.search(line)
    if m:
        return {
            "value_num": None,
            "value_text": None,
            "unit": normalize_units(m.group("unit")),
            "range_low": float(m.group("low")),
            "range_high": float(m.group("high")),
        }

    m = _PCT_PAT.search(line)
    if m:
        return {
            "value_num": float(m.group("num")),
            "value_text": None,
            "unit": "%",
            "range_low": None,
            "range_high": None,
        }

    m = _NUM_UNIT_PAT.search(line)
    if m:
        return {
            "value_num": float(m.group("num")),
            "value_text": None,
            "unit": normalize_units(m.group("unit")),
            "range_low": None,
            "range_high": None,
        }

    m = _TEMP_RANGE_PAT.search(line)
    if m:
        return {
            "value_num": None,
            "value_text": None,
            "unit": "C",
            "range_low": float(m.group("low")),
            "range_high": float(m.group("high")),
        }
    m = _TEMP_SINGLE_PAT.search(line)
    if m:
        return {
            "value_num": float(m.group("num")),
            "value_text": None,
            "unit": "C",
            "range_low": None,
            "range_high": None,
        }

    return {
        "value_num": None,
        "value_text": line.strip()[:500],
        "unit": None,
        "range_low": None,
        "range_high": None,
    }


def conflict_detect(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Simple v1 de-dupe: keep first best candidate for each (param_code, evidence_text)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        code = str(it.get("param_code") or "").strip()
        ev = str(it.get("evidence_text") or "").strip()
        key = (code, ev)
        if not code or not ev or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def extract_from_text(text: str, ontology: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    ont = ontology or PARAM_ONTOLOGY
    t = str(text or "")
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    out: list[dict[str, Any]] = []
    for line in lines:
        lower = line.lower()
        for code, meta in ont.items():
            aliases = [str(x).lower() for x in (meta.get("aliases") or [])]
            if not _contains_any(lower, aliases):
                continue
            v = _extract_value(line)
            out.append(
                {
                    "param_code": str(code),
                    "value_num": v.get("value_num"),
                    "value_text": v.get("value_text"),
                    "unit": v.get("unit"),
                    "range_low": v.get("range_low"),
                    "range_high": v.get("range_high"),
                    "conditions": {},
                    "evidence_text": line[:500],
                    "confidence": 0.70,
                }
            )
    return conflict_detect(out)

