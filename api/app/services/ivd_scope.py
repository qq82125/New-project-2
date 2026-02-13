from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.mapping import ProductRecord

IVD_RULE_VERSION = 'ivd-v1'

_STRONG_IVD_PATTERNS = (
    r'体外诊断',
    r'\bivd\b',
    r'in[\s\-]?vitro',
    r'诊断试剂',
    r'检测试剂',
    r'试剂盒',
    r'校准品',
    r'质控品',
    r'核酸(检|测|扩增)',
    r'pcr',
    r'分子诊断',
)

_INSTRUMENT_PATTERNS = (
    r'分析仪',
    r'检测仪',
    r'测定仪',
    r'免疫分析',
    r'化学发光',
    r'血球',
    r'血凝',
    r'生化',
    r'poct',
)

_SOFTWARE_PATTERNS = (
    r'医疗软件',
    r'诊断软件',
    r'检验软件',
    r'l[ai]s',
    r'算法',
    r'软件',
    r'平台',
    r'系统',
)

_DIAG_CONTEXT_PATTERNS = (
    r'诊断',
    r'检测',
    r'检验',
    r'分析',
    r'测定',
    r'病原',
    r'核酸',
    r'免疫',
    r'生化',
    r'血液',
)

_NEGATIVE_PATTERNS = (
    r'骨科',
    r'口腔',
    r'牙科',
    r'眼科',
    r'注射器',
    r'缝合',
    r'假体',
    r'植入',
    r'心脏支架',
)


def _match_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _compact_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        if len(parts) >= 64:
            break
        txt = str(value).strip()
        if txt:
            parts.append(txt)
    return ' | '.join(parts)


def _candidate_text(
    *,
    name: str | None,
    class_name: str | None,
    category: str | None,
    reg_no: str | None,
    raw: dict[str, Any] | None,
) -> str:
    fields = [name or '', class_name or '', category or '', reg_no or '']
    raw_text = _compact_text(raw or {})
    fields.append(raw_text)
    return ' | '.join([x for x in fields if x]).lower()


def is_ivd_candidate_text(text: str) -> bool:
    text = (text or '').strip().lower()
    if not text:
        return False

    if '6840' in text:
        return True
    if _match_any(text, _STRONG_IVD_PATTERNS):
        return True

    has_diag_context = _match_any(text, _DIAG_CONTEXT_PATTERNS)
    if has_diag_context and _match_any(text, _INSTRUMENT_PATTERNS):
        return True
    if has_diag_context and _match_any(text, _SOFTWARE_PATTERNS):
        return True

    if _match_any(text, _NEGATIVE_PATTERNS):
        return False
    return False


@dataclass
class IvdDecision:
    is_ivd: bool
    reason: str
    ivd_version: str
    matched: list[str]


def classify_ivd_raw_record(raw: dict[str, Any], record: ProductRecord | None = None) -> IvdDecision:
    text = _candidate_text(
        name=record.name if record else str(raw.get('name') or raw.get('product_name') or raw.get('产品名称') or ''),
        class_name=record.class_name if record else str(raw.get('class') or raw.get('class_name') or raw.get('管理类别') or ''),
        category=str(raw.get('category') or raw.get('cplb') or raw.get('flbm') or raw.get('类别') or ''),
        reg_no=record.reg_no if record else str(raw.get('reg_no') or raw.get('registration_no') or raw.get('注册证编号') or ''),
        raw=raw,
    )
    text0 = (text or '').strip().lower()
    matched: list[str] = []

    if '6840' in text0:
        matched.append('category_code:6840')
        return IvdDecision(True, 'matched_category_code_6840', IVD_RULE_VERSION, matched)

    for p in _STRONG_IVD_PATTERNS:
        if re.search(p, text0, flags=re.IGNORECASE):
            matched.append(f'strong:{p}')
    if matched:
        return IvdDecision(True, 'matched_strong_ivd_keyword', IVD_RULE_VERSION, matched)

    has_diag_context = _match_any(text0, _DIAG_CONTEXT_PATTERNS)
    has_instrument = _match_any(text0, _INSTRUMENT_PATTERNS)
    has_software = _match_any(text0, _SOFTWARE_PATTERNS)
    if has_diag_context and has_instrument:
        return IvdDecision(True, 'matched_diag_context_plus_instrument', IVD_RULE_VERSION, ['diag_context', 'instrument'])
    if has_diag_context and has_software:
        return IvdDecision(True, 'matched_diag_context_plus_software', IVD_RULE_VERSION, ['diag_context', 'software'])

    if _match_any(text0, _NEGATIVE_PATTERNS):
        return IvdDecision(False, 'matched_negative_non_ivd_keyword', IVD_RULE_VERSION, [])
    return IvdDecision(False, 'no_ivd_signal', IVD_RULE_VERSION, [])


def is_ivd_raw_record(raw: dict[str, Any], record: ProductRecord | None = None) -> bool:
    return classify_ivd_raw_record(raw, record=record).is_ivd
