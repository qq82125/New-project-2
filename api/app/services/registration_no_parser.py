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
_LEGACY_RE = re.compile(
    r"^(?P<prefix>[\u4e00-\u9fff]{0,8})药监械(?P<origin>准|进|许)?字(?P<year>\d{4})第(?P<body>\d{4,})号$"
)


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
    parse_version: int = _PARSE_VERSION
    registration_no_raw: str | None = None


def _unknown(reg_no_norm: str | None) -> ParsedRegistrationNo:
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


def parse_registration_no(reg_no_norm: str) -> ParsedRegistrationNo:
    normalized = str(reg_no_norm or "").strip()
    if not normalized:
        return _unknown(None)

    m_new = _NEW_CERT_RE.match(normalized)
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
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    m_filing = _FILING_RE.match(normalized)
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
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    m_legacy = _LEGACY_RE.match(normalized)
    if m_legacy:
        legacy_body = m_legacy.group("body")
        category_code = legacy_body[:3] if len(legacy_body) >= 7 else None
        serial_no = legacy_body[3:] if category_code else legacy_body
        mclass = int(category_code[0]) if category_code and category_code[0] in {"1", "2", "3"} else None
        return ParsedRegistrationNo(
            regno_type="registration",
            origin_type=_origin_type(m_legacy.group("origin")),
            approval_level=_approval_level(m_legacy.group("prefix")),
            management_class=mclass,
            first_year=int(m_legacy.group("year")),
            category_code=category_code,
            serial_no=serial_no,
            is_legacy_format=True,
            parse_ok=True,
            parse_version=_PARSE_VERSION,
            registration_no_raw=normalized,
        )

    return _unknown(normalized)
