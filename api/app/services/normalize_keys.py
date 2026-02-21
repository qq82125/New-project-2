from __future__ import annotations

import re
import unicodedata


# Only split on separators that are unlikely to be part of the canonical key itself.
# Do NOT split on "/" because some sources encode numbers like "2023-12/34".
_REG_NO_SPLIT_RE = re.compile(r"[，,;；|\\s]+")
_REG_NO_MULTI_START_RE = re.compile(r"[\u4e00-\u9fff]{1,6}械")


def normalize_registration_no(text: str | None) -> str | None:
    """Normalize registration/filing numbers into a canonical match key.

    Design goals:
    - Stable: deterministic output for matching/joining.
    - Conservative: keeps only digits, ASCII letters, and CJK Unified Ideographs.
    - Practical: eliminates spacing, full-width variants, and common separators.

    Extra guard:
    - If the input accidentally contains *multiple* concatenated registration numbers (common in UDI exports),
      we attempt to extract the first plausible segment to avoid blowing through VARCHAR limits.
    """
    if text is None:
        return None
    candidates = extract_registration_no_candidates(text)
    return candidates[0] if candidates else None


def _normalize_reg_token(raw_token: str | None) -> str | None:
    if raw_token is None:
        return None
    s = str(raw_token).strip()
    if not s:
        return None

    # NFKC normalizes full-width chars (e.g. "Ａ" -> "A") and common punctuation variants.
    s = unicodedata.normalize("NFKC", s)
    s = "".join(ch for ch in s if not ch.isspace()).upper()

    out = []
    for ch in s:
        o = ord(ch)
        if "0" <= ch <= "9":
            out.append(ch)
        elif "A" <= ch <= "Z":
            out.append(ch)
        elif 0x4E00 <= o <= 0x9FFF:
            out.append(ch)
    normalized = "".join(out)
    if not normalized:
        return None

    starts = [m.start() for m in _REG_NO_MULTI_START_RE.finditer(normalized)]
    if len(starts) >= 2:
        st = starts[0]
        ed = starts[1]
        seg = normalized[st:ed]
        if 0 < len(seg) <= 120 and sum(ch.isdigit() for ch in seg) >= 6:
            return seg

    if len(normalized) <= 120:
        return normalized

    if starts:
        for i, st in enumerate(starts):
            ed = starts[i + 1] if i + 1 < len(starts) else len(normalized)
            seg = normalized[st:ed]
            if 0 < len(seg) <= 120 and sum(ch.isdigit() for ch in seg) >= 6:
                return seg
    return None


def extract_registration_no_candidates(text: str | None) -> list[str]:
    """Return ordered normalized candidates; used by ingest guards to detect multi-reg rows."""
    if text is None:
        return []
    raw = str(text).strip()
    if not raw:
        return []

    tokens = [t.strip() for t in _REG_NO_SPLIT_RE.split(raw) if t and t.strip()]
    if not tokens:
        tokens = [raw]

    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        n = _normalize_reg_token(token)
        if n and n not in seen:
            out.append(n)
            seen.add(n)

    if out:
        return out
    n = _normalize_reg_token(raw)
    return [n] if n else []
