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
    raw = str(text).strip()
    if not raw:
        return None

    # Prefer the first token when common separators exist (prevents accidental multi-value joins).
    first_token = _REG_NO_SPLIT_RE.split(raw, maxsplit=1)[0]
    s = first_token.strip()
    if not s:
        return None

    # NFKC normalizes full-width chars (e.g. "Ａ" -> "A") and common punctuation variants.
    s = unicodedata.normalize("NFKC", s)

    # Remove all whitespace and uppercase ASCII letters.
    s = "".join(ch for ch in s if not ch.isspace()).upper()

    # Keep: digits, A-Z, and CJK ideographs. Drop everything else (separators/punctuation/brackets).
    out = []
    for ch in s:
        o = ord(ch)
        if "0" <= ch <= "9":
            out.append(ch)
        elif "A" <= ch <= "Z":
            out.append(ch)
        elif 0x4E00 <= o <= 0x9FFF:
            out.append(ch)
        # else: drop

    normalized = "".join(out)
    if not normalized:
        return None

    # If the string contains multiple "省/国...械" anchors, treat it as concatenated multi-values
    # and extract the first plausible segment, even if it doesn't exceed 120 chars.
    starts = [m.start() for m in _REG_NO_MULTI_START_RE.finditer(normalized)]
    if len(starts) >= 2:
        st = starts[0]
        ed = starts[1]
        seg = normalized[st:ed]
        if 0 < len(seg) <= 120 and sum(ch.isdigit() for ch in seg) >= 6:
            return seg

    # Hard length guard: registration_no columns are VARCHAR(120) in this repo.
    if len(normalized) <= 120:
        return normalized

    # Attempt to extract the first segment when multiple registration numbers were concatenated.
    # Example from UDI: "苏械注准2016...苏械注准2015...苏械注准2017..."
    if starts:
        for i, st in enumerate(starts):
            ed = starts[i + 1] if i + 1 < len(starts) else len(normalized)
            seg = normalized[st:ed]
            if 0 < len(seg) <= 120 and sum(ch.isdigit() for ch in seg) >= 6:
                return seg

    # Give up: returning None is safer than truncating and creating a wrong anchor.
    return None
