from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any


_TEMP_RANGE_RE = re.compile(
    r"(?P<min>-?\d+(?:\.\d+)?)\s*(?:~|-|至|到)\s*(?P<max>-?\d+(?:\.\d+)?)\s*(?:°?\s*[cC]|℃)?"
)
_TEMP_LE_RE = re.compile(r"(?:≤|<=)\s*(?P<max>-?\d+(?:\.\d+)?)\s*(?:°?\s*[cC]|℃)?")
_TEMP_GE_RE = re.compile(r"(?:≥|>=)\s*(?P<min>-?\d+(?:\.\d+)?)\s*(?:°?\s*[cC]|℃)?")
_TRANSPORT_HINTS = ("运输", "运送", "transport", "shipping", "transit", "cold chain")
_STORAGE_HINTS = ("储存", "贮存", "storage", "store")


def _as_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _load_json_like(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return raw
    return raw


def _extract_storage_objects(raw: Any) -> list[dict[str, Any]]:
    src = _load_json_like(raw)
    if isinstance(src, dict):
        for key in ("storages", "storage", "storageList", "items"):
            maybe = src.get(key)
            if isinstance(maybe, list):
                src = maybe
                break
    if not isinstance(src, list):
        return []
    out: list[dict[str, Any]] = []
    for item in src:
        if isinstance(item, dict):
            out.append(item)
    return out


def _extract_root_temp_fields(raw: Any) -> tuple[float | None, float | None, float | None, float | None]:
    src = _load_json_like(raw)
    if not isinstance(src, dict):
        return (None, None, None, None)

    def pick(*keys: str) -> float | None:
        for k in keys:
            if k in src:
                v = _to_float(src.get(k))
                if v is not None:
                    return v
        return None

    return (
        pick("storageMin", "storage_min", "storage_temp_min", "minTemp", "min_temp"),
        pick("storageMax", "storage_max", "storage_temp_max", "maxTemp", "max_temp"),
        pick("transportMin", "transport_min", "transport_temp_min", "shippingMin", "logisticsMin"),
        pick("transportMax", "transport_max", "transport_temp_max", "shippingMax", "logisticsMax"),
    )


def parse_storage_json(raw: Any) -> dict[str, Any]:
    storages = _extract_storage_objects(raw)
    notes: list[str] = []
    storage_mins: list[float] = []
    storage_maxs: list[float] = []
    transport_mins: list[float] = []
    transport_maxs: list[float] = []

    def _push_temp(stype: str, mn: float | None, mx: float | None, extra_text: str = "") -> None:
        scope_text = f"{stype} {extra_text}".lower()
        is_transport = any(token in scope_text for token in _TRANSPORT_HINTS)
        is_storage = any(token in scope_text for token in _STORAGE_HINTS)
        write_both = is_transport and is_storage
        if mn is not None:
            if write_both:
                transport_mins.append(mn)
                storage_mins.append(mn)
            else:
                (transport_mins if is_transport else storage_mins).append(mn)
        if mx is not None:
            if write_both:
                transport_maxs.append(mx)
                storage_maxs.append(mx)
            else:
                (transport_maxs if is_transport else storage_maxs).append(mx)

    for item in storages:
        stype = (_as_text(item.get("type")) or "").lower()
        rng = _as_text(item.get("range")) or ""
        note = _as_text(item.get("note"))
        if note:
            notes.append(note)
        if rng:
            notes.append(rng)

        mn = _to_float(item.get("min"))
        mx = _to_float(item.get("max"))
        if mn is None:
            mn = _to_float(item.get("minTemp") or item.get("storageMin") or item.get("transportMin"))
        if mx is None:
            mx = _to_float(item.get("maxTemp") or item.get("storageMax") or item.get("transportMax"))

        if mn is None and mx is None and rng:
            m = _TEMP_RANGE_RE.search(rng)
            if m:
                mn = _to_float(m.group("min"))
                mx = _to_float(m.group("max"))
            else:
                m_le = _TEMP_LE_RE.search(rng)
                m_ge = _TEMP_GE_RE.search(rng)
                if m_le:
                    mx = _to_float(m_le.group("max"))
                if m_ge:
                    mn = _to_float(m_ge.group("min"))

        _push_temp(stype, mn, mx, f"{rng} {note or ''}")

    rs_min, rs_max, rt_min, rt_max = _extract_root_temp_fields(raw)
    if rs_min is not None:
        storage_mins.append(rs_min)
    if rs_max is not None:
        storage_maxs.append(rs_max)
    if rt_min is not None:
        transport_mins.append(rt_min)
    if rt_max is not None:
        transport_maxs.append(rt_max)

    if not storages:
        raw_text = _as_text(raw)
        if raw_text:
            m = _TEMP_RANGE_RE.search(raw_text)
            if m:
                storage_mins.append(float(m.group("min")))
                storage_maxs.append(float(m.group("max")))
            else:
                m_le = _TEMP_LE_RE.search(raw_text)
                m_ge = _TEMP_GE_RE.search(raw_text)
                if m_le:
                    storage_maxs.append(float(m_le.group("max")))
                if m_ge:
                    storage_mins.append(float(m_ge.group("min")))
            notes.append(raw_text)
    else:
        raw_text = _as_text(raw)

    # Heuristic fallback: if transport context appears but explicit transport temps are absent,
    # reuse parsed storage bounds as transport bounds to avoid dropping actionable cold-chain info.
    text_blob = " ".join([str(x) for x in notes])
    if raw_text:
        text_blob = f"{text_blob} {raw_text}"
    if (not transport_mins and not transport_maxs) and (storage_mins or storage_maxs):
        lower_blob = text_blob.lower()
        if any(h in lower_blob for h in _TRANSPORT_HINTS):
            transport_mins = list(storage_mins)
            transport_maxs = list(storage_maxs)

    storage_note = None
    if notes:
        uniq: list[str] = []
        seen: set[str] = set()
        for n in notes:
            s = str(n or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            uniq.append(s)
        storage_note = "; ".join(uniq[:10]) if uniq else None

    return {
        "STORAGE_TEMP_MIN_C": min(storage_mins) if storage_mins else None,
        "STORAGE_TEMP_MAX_C": max(storage_maxs) if storage_maxs else None,
        "TRANSPORT_TEMP_MIN_C": min(transport_mins) if transport_mins else None,
        "TRANSPORT_TEMP_MAX_C": max(transport_maxs) if transport_maxs else None,
        "STORAGE_NOTE": storage_note,
    }


def parse_packing_json(raw: Any) -> dict[str, Any]:
    src = _load_json_like(raw)
    if isinstance(src, dict):
        for key in ("packings", "packingList", "packages", "items"):
            maybe = src.get(key)
            if isinstance(maybe, list):
                src = maybe
                break
    if not isinstance(src, list):
        return {"PACKAGE_LEVEL": None, "PACKAGE_UNIT": None, "PACKAGE_QTY": None}

    rows = [item for item in src if isinstance(item, dict)]
    if not rows:
        return {"PACKAGE_LEVEL": None, "PACKAGE_UNIT": None, "PACKAGE_QTY": None}

    # Prefer primary/smallest sales unit.
    def _rank(item: dict[str, Any]) -> tuple[int, int]:
        level = (_as_text(item.get("package_level")) or "").lower()
        qty = _to_float(item.get("contains_qty"))
        primary = 0 if level in {"ea", "single", "unit", "最小销售单元", "primary", "盒", "瓶", "袋", "支"} else 1
        qty_rank = int(qty) if qty is not None else 10**9
        return (primary, qty_rank)

    row = sorted(rows, key=_rank)[0]
    level = _as_text(row.get("package_level"))
    unit = _as_text(row.get("package_unit")) or _as_text(row.get("unit")) or _as_text(row.get("contains_unit"))
    qty_raw = _to_float(row.get("contains_qty"))
    qty = str(int(qty_raw)) if qty_raw is not None and float(qty_raw).is_integer() else (_as_text(qty_raw) if qty_raw is not None else None)
    return {"PACKAGE_LEVEL": level, "PACKAGE_UNIT": unit, "PACKAGE_QTY": qty}


def normalize_mjfs(raw: Any) -> str | None:
    text = _as_text(raw)
    if not text:
        return None
    normalized = re.sub(r"\s+", "", text).upper()
    mapping = {
        "环氧乙烷": "EO",
        "EO": "EO",
        "ETO": "EO",
        "蒸汽灭菌": "STEAM",
        "湿热灭菌": "STEAM",
        "高压蒸汽灭菌": "STEAM",
        "辐照灭菌": "RADIATION",
    }
    for k, v in mapping.items():
        if k in normalized:
            return v
    return text.strip()


def normalize_brand(raw: Any) -> str | None:
    text = _as_text(raw)
    if not text:
        return None
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff]+", "", text).strip(" /|;,")
    return cleaned or None
