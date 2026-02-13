from __future__ import annotations

import re
from typing import Any, Mapping

from app.services.ivd_dictionary import (
    INSTRUMENT_EXCLUDE,
    IVD_GLOBAL_EXCLUDE,
    IVD_INSTRUMENT_FALLBACK_INCLUDE,
    IVD_INSTRUMENT_INCLUDE,
    IVD_REAGENT_INCLUDE,
    IVD_SOFTWARE_FALLBACK_INCLUDE,
    IVD_SOFTWARE_INCLUDE,
    NGS_INCLUDE,
    PCR_INCLUDE,
    POCT_INCLUDE,
    SOFTWARE_EXCLUDE,
)

VERSION = 3


def _normalize_text(value: Any) -> str:
    return str(value or '').strip().lower()


def _match_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for kw in keywords:
        kw_norm = kw.lower()
        # ASCII keywords use token boundary to avoid accidental substring hits
        # like matching "lis" inside "elisa".
        if re.fullmatch(r'[a-z0-9\\-]+', kw_norm):
            if re.search(rf'(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])', text):
                hits.append(kw)
            continue
        if kw_norm in text:
            hits.append(kw)
    return hits


def _extract_class_code(payload: Mapping[str, Any]) -> str:
    code = payload.get('classification_code')
    if code is None:
        code = payload.get('class_code')
    return str(code or '').strip()


def classify_ivd(payload: Mapping[str, Any]) -> dict[str, Any]:
    class_code = _extract_class_code(payload)
    name = _normalize_text(payload.get('name'))
    model = _normalize_text(payload.get('model'))
    specification = _normalize_text(payload.get('specification'))
    category = _normalize_text(payload.get('category'))
    scope_text = ' '.join(x for x in (name, model, specification, category) if x)

    ivd_block: dict[str, Any] = {'by': 'rule', 'code': class_code, 'category': None}
    is_ivd = False
    ivd_category: str | None = None

    global_exclude_hits = _match_hits(scope_text, IVD_GLOBAL_EXCLUDE)
    if global_exclude_hits:
        return {
            'is_ivd': False,
            'ivd_category': None,
            'ivd_subtypes': [],
            'confidence': 0.99,
            'source': 'RULE',
            'reason': {
                'ivd': {
                    'by': 'global_exclude',
                    'code': class_code,
                    'category': None,
                    'exclude_hits': global_exclude_hits,
                },
                'subtypes': [],
                'needs_review': False,
            },
            'version': VERSION,
        }

    if class_code.startswith('22'):
        is_ivd = True
        ivd_category = 'reagent'
        ivd_block = {'by': 'class_code', 'code': '22', 'category': ivd_category}
    elif class_code.startswith('6840'):
        is_ivd = True
        ivd_category = 'reagent'
        ivd_block = {'by': 'class_code', 'code': '6840', 'category': ivd_category}
    elif class_code.startswith('07'):
        include_hits = _match_hits(name, IVD_INSTRUMENT_INCLUDE)
        exclude_hits = _match_hits(name, INSTRUMENT_EXCLUDE)
        if include_hits and not exclude_hits:
            is_ivd = True
            ivd_category = 'instrument'
            ivd_block = {'by': 'class_code+keyword', 'code': '07', 'category': ivd_category, 'hits': include_hits}
        else:
            ivd_block = {'by': 'class_code+keyword', 'code': '07', 'category': None, 'exclude_hits': exclude_hits}
    elif class_code.startswith('21'):
        include_hits = _match_hits(name, IVD_SOFTWARE_INCLUDE)
        exclude_hits = _match_hits(name, SOFTWARE_EXCLUDE)
        if include_hits and not exclude_hits:
            is_ivd = True
            ivd_category = 'software'
            ivd_block = {'by': 'class_code+keyword', 'code': '21', 'category': ivd_category, 'hits': include_hits}
        else:
            ivd_block = {'by': 'class_code+keyword', 'code': '21', 'category': None, 'exclude_hits': exclude_hits}
    elif not class_code:
        reagent_hits = _match_hits(name, IVD_REAGENT_INCLUDE)
        inst_hits = _match_hits(name, IVD_INSTRUMENT_FALLBACK_INCLUDE)
        inst_exclude_hits = _match_hits(name, INSTRUMENT_EXCLUDE)
        sw_hits = _match_hits(name, IVD_SOFTWARE_FALLBACK_INCLUDE)
        sw_exclude_hits = _match_hits(name, SOFTWARE_EXCLUDE)
        if reagent_hits:
            is_ivd = True
            ivd_category = 'reagent'
            ivd_block = {'by': 'keyword_fallback', 'code': class_code, 'category': ivd_category, 'hits': reagent_hits}
        elif inst_hits and not inst_exclude_hits:
            is_ivd = True
            ivd_category = 'instrument'
            ivd_block = {'by': 'keyword_fallback', 'code': class_code, 'category': ivd_category, 'hits': inst_hits}
        elif sw_hits and not sw_exclude_hits:
            is_ivd = True
            ivd_category = 'software'
            ivd_block = {'by': 'keyword_fallback', 'code': class_code, 'category': ivd_category, 'hits': sw_hits}
        else:
            ivd_block = {'by': 'fallback', 'code': class_code, 'category': None}
    else:
        ivd_block = {'by': 'fallback', 'code': class_code, 'category': None}

    subtype_items: list[dict[str, Any]] = []
    ivd_subtypes: list[str] = []
    if is_ivd:
        for stype, keywords in (('NGS', NGS_INCLUDE), ('PCR', PCR_INCLUDE), ('POCT', POCT_INCLUDE)):
            hits = _match_hits(name, keywords)
            if hits:
                ivd_subtypes.append(stype)
                subtype_items.append({'type': stype, 'hits': hits, 'field': 'name'})

    return {
        'is_ivd': is_ivd,
        'ivd_category': ivd_category,
        'ivd_subtypes': ivd_subtypes,
        'confidence': (
            0.95 if is_ivd and class_code.startswith(('22', '6840'))
            else 0.85 if is_ivd
            else 0.80 if class_code
            else 0.50
        ),
        'source': 'RULE',
        'reason': {
            'ivd': ivd_block,
            'subtypes': subtype_items,
            'needs_review': not is_ivd and not class_code,
        },
        'version': VERSION,
    }
