from __future__ import annotations

import re
from dataclasses import dataclass

_PARSE_VERSION = 1

_NEW_CERT_RE = re.compile(
    r"^(?P<prefix>[\u4e00-\u9fff]{0,6})械注(?P<origin>准|进|许)(?P<year>\d{4})(?P<mclass>[123])(?P<category>\d{2})(?P<serial>\d{4,})$"
)
_FILING_RE = re.compile(
    r"^(?P<prefix>[\u4e00-\u9fff]{0,6})械备(?P<year>\d{4})(?P<serial>\d{3,})$"
)
_LEGACY_RE_LIST = [
    re.compile(
        r"^(?P<prefix>[\u4e00-\u9fff]{0,8})药监械(?P<origin>准|进|许)?字(?P<year>\d{4})第(?P<body>\d{4,})号$"
    ),
    re.compile(
        r"^(?P<prefix>[\u4e00-\u9fff]{0,8})食药监械(?P<origin>准|进|许)?字(?P<year>\d{4})第(?P<body>\d{4,})号$"
    ),
    re.compile(
        r"^(?P<prefix>[\u4e00-\u9fff]{0,8})药管械(?P<origin>准|进|许)?字(?P<year>\d{4})第(?P<body>\d{4,})号$"
    ),
    re.compile(
        r"^(?P<prefix>[\u4e00-\u9fff]{0,8})食药管械(?P<origin>准|进|许)?字(?P<year>\d{4})第(?P<body>\d{4,})号$"
    ),
]
_ACTION_SUFFIX_RE = re.compile(r"[（(]?(?P<suffix>[更延补])[）)]?$")
_LEGACY_CLASSIFIED_HINTS = (
    "国食药监械",
    "国食药管械",
    "食药监械",
    "食药管械",
    "国药监械",
    "药监械",
    "药管械",
    "国家药监局",
)
_ISSUER_ALIAS_RULES: list[tuple[str, str]] = [
    ("国家药监局", "NMPA_LEGACY_ISSUER"),
    ("国食药监械", "NMPA_LEGACY_ISSUER"),
    ("国食药管械", "NMPA_LEGACY_ISSUER"),
    ("国药监械", "NMPA_LEGACY_ISSUER"),
    ("食药监械", "NMPA_LEGACY_ISSUER"),
    ("食药管械", "NMPA_LEGACY_ISSUER"),
    ("药监械", "NMPA_LEGACY_ISSUER"),
    ("药管械", "NMPA_LEGACY_ISSUER"),
]


@dataclass(frozen=True)
class ParsedRegistrationNo:
    regno_type: str
    origin_type: str
    approval_level: str
    management_class: int | None
    first_year: int | None
    category_code: str | None
    serial_no: str | None
    is_legacy_format: bool
    parse_ok: bool
    parse_level: str = "FAIL"
    parse_confidence: float = 0.0
    parse_reason: str = "UNKNOWN_PATTERN"
    issuer_alias: str | None = None
    action_suffix: str | None = None
    legacy_seq: str | None = None
    parse_version: int = _PARSE_VERSION
    registration_no_raw: str | None = None


@dataclass(frozen=True)
class LegacyNormalizationResult:
    normalized: str
    issuer_alias: str | None
    action_suffix: str | None


def _unknown(
    reg_no_norm: str | None,
    *,
    reason: str = "UNKNOWN_PATTERN",
    issuer_alias: str | None = None,
    action_suffix: str | None = None,
) -> ParsedRegistrationNo:
    return ParsedRegistrationNo(
        regno_type="unknown",
        origin_type="unknown",
        approval_level="unknown",
        management_class=None,
        first_year=None,
        category_code=None,
        serial_no=None,
        is_legacy_format=False,
        parse_ok=False,
        parse_level="FAIL",
        parse_confidence=0.0,
        parse_reason=reason,
        issuer_alias=issuer_alias,
        action_suffix=action_suffix,
        legacy_seq=None,
        parse_version=_PARSE_VERSION,
        registration_no_raw=reg_no_norm,
    )


def _approval_level(prefix: str) -> str:
    p = (prefix or "").strip()
    if not p:
        return "unknown"
    if p.startswith("国"):
        return "national"
    return "provincial"


def _origin_type(origin: str | None) -> str:
    if origin == "准":
        return "domestic"
    if origin == "进":
        return "import"
    if origin == "许":
        return "permit"
    return "unknown"


def _issuer_alias(text: str) -> str | None:
    for token, alias in _ISSUER_ALIAS_RULES:
        if token in text:
            return alias
    return None


def normalize_for_legacy_variants(text: str) -> LegacyNormalizationResult:
    base = str(text or "").strip()
    if not base:
        return LegacyNormalizationResult(normalized="", issuer_alias=None, action_suffix=None)
    cleaned = (
        base.replace("（", "(")
        .replace("）", ")")
        .replace("【", "(")
        .replace("】", ")")
        .replace(" ", "")
        .replace("\u3000", "")
    )

    action_suffix: str | None = None
    found = re.findall(r"\((更|延|补)\)", cleaned)
    if found:
        action_suffix = found[-1]
        cleaned = re.sub(r"\((更|延|补)\)", "", cleaned)
    m_suffix = _ACTION_SUFFIX_RE.search(cleaned)
    if m_suffix:
        action_suffix = action_suffix or m_suffix.group("suffix")
        cleaned = cleaned[: m_suffix.start()]

    alias = _issuer_alias(cleaned)
    return LegacyNormalizationResult(normalized=cleaned, issuer_alias=alias, action_suffix=action_suffix)


def parse_registration_no(reg_no_norm: str) -> ParsedRegistrationNo:
    normalized = str(reg_no_norm or "").strip()
    if not normalized:
        return _unknown(None, reason="REGNO_MISSING")

    norm = normalize_for_legacy_variants(normalized)
    candidate = norm.normalized

    m_new = _NEW_CERT_RE.match(candidate)
    if m_new:
        return ParsedRegistrationNo(
            regno_type="registration",
            origin_type=_origin_type(m_new.group("origin")),
            approval_level=_approval_level(m_new.group("prefix")),
            management_class=int(m_new.group("mclass")),
            first_year=int(m_new.group("year")),
            category_code=m_new.group("category"),
            serial_no=m_new.group("serial"),
            is_legacy_format=False,
            parse_ok=True,
            parse_level="FULL",
            parse_confidence=1.0,
            parse_reason="NEW_CERT_FULL",
            issuer_alias=norm.issuer_alias,
            action_suffix=norm.action_suffix,
            legacy_seq=None,
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    m_filing = _FILING_RE.match(candidate)
    if m_filing:
        return ParsedRegistrationNo(
            regno_type="filing",
            origin_type="filing",
            approval_level=_approval_level(m_filing.group("prefix")),
            management_class=None,
            first_year=int(m_filing.group("year")),
            category_code=None,
            serial_no=m_filing.group("serial"),
            is_legacy_format=False,
            parse_ok=True,
            parse_level="FULL",
            parse_confidence=0.98,
            parse_reason="FILING_FULL",
            issuer_alias=norm.issuer_alias,
            action_suffix=norm.action_suffix,
            legacy_seq=None,
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    for legacy_re in _LEGACY_RE_LIST:
        m_legacy = legacy_re.match(candidate)
        if not m_legacy:
            continue
        legacy_body = m_legacy.group("body")
        prefix = m_legacy.group("prefix")
        origin = m_legacy.group("origin")
        category_code = legacy_body[:3] if len(legacy_body) >= 7 else None
        serial_no = legacy_body[3:] if category_code else legacy_body
        mclass = int(category_code[0]) if category_code and category_code[0] in {"1", "2", "3"} else None
        is_full_legacy = bool(category_code and mclass is not None and serial_no)
        parse_level = "FULL" if is_full_legacy else "PARTIAL"
        parse_reason = "LEGACY_VARIANT_FULL" if is_full_legacy else "LEGACY_VARIANT"
        confidence = 0.92 if is_full_legacy else 0.78
        if norm.action_suffix:
            parse_reason = "LEGACY_ACTION_SUFFIX"
            confidence = min(confidence, 0.8)
        elif norm.issuer_alias:
            parse_reason = "ISSUER_ALIAS" if not is_full_legacy else "LEGACY_VARIANT_FULL"
        return ParsedRegistrationNo(
            regno_type="registration",
            origin_type=_origin_type(origin),
            approval_level=_approval_level(prefix),
            management_class=(mclass if is_full_legacy else None),
            first_year=int(m_legacy.group("year")),
            category_code=(category_code if is_full_legacy else None),
            serial_no=serial_no,
            is_legacy_format=True,
            parse_ok=True,
            parse_level=parse_level,
            parse_confidence=confidence,
            parse_reason=parse_reason,
            issuer_alias=norm.issuer_alias,
            action_suffix=norm.action_suffix,
            legacy_seq=legacy_body,
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    contains_legacy_shape = ("药监械" in candidate and "字" in candidate and "第" in candidate) or any(
        token in candidate for token in _LEGACY_CLASSIFIED_HINTS
    )
    if contains_legacy_shape:
        reason = "OLD_PATTERN_CLASSIFIED" if ("药监械" in candidate and "字" in candidate and "第" in candidate) else "LEGACY_VARIANT"
        return ParsedRegistrationNo(
            regno_type="registration",
            origin_type=_origin_type(next((x for x in ("准", "进", "许") if x in candidate), None)),
            approval_level=_approval_level(candidate[:2]),
            management_class=None,
            first_year=None,
            category_code=None,
            serial_no=None,
            is_legacy_format=True,
            parse_ok=True,
            parse_level="CLASSIFIED",
            parse_confidence=0.55,
            parse_reason=reason,
            issuer_alias=norm.issuer_alias,
            action_suffix=norm.action_suffix,
            legacy_seq=None,
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    return _unknown(
        normalized,
        reason=("ISSUER_ALIAS" if norm.issuer_alias else "UNKNOWN_PATTERN"),
        issuer_alias=norm.issuer_alias,
        action_suffix=norm.action_suffix,
    )
