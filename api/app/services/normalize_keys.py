from __future__ import annotations

import unicodedata


def normalize_registration_no(text: str | None) -> str | None:
    """Normalize registration/filing numbers into a canonical match key.

    Design goals:
    - Stable: deterministic output for matching/joining.
    - Conservative: keeps only digits, ASCII letters, and CJK Unified Ideographs.
    - Practical: eliminates spacing, full-width variants, and common separators.
    """
    if text is None:
        return None
    s = str(text).strip()
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
    return normalized or None

