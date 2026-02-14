from __future__ import annotations

from typing import Any, Callable, Mapping

from app.services.ivd_classifier import VERSION as INTERNAL_RULE_VERSION, classify_ivd

DEFAULT_VERSION = 'ivd_v1_20260213'


def _extract_class_code(record: Mapping[str, Any]) -> str:
    v = record.get('classification_code')
    if v is None:
        v = record.get('class_code')
    return str(v or '').strip()


def _strict_needs_review(*, record: Mapping[str, Any], decision: Mapping[str, Any]) -> bool:
    # Default strictness: if not IVD and the rule path is "fallback-ish", mark needs_review.
    if bool(decision.get('is_ivd')):
        return False

    reason = decision.get('reason') if isinstance(decision.get('reason'), dict) else {}
    if bool(reason.get('needs_review')):
        return True

    ivd_block = reason.get('ivd') if isinstance(reason.get('ivd'), dict) else {}
    by = str(ivd_block.get('by') or '').strip()
    code = _extract_class_code(record)
    if not code and by in {'fallback', 'keyword_fallback'}:
        return True
    if not code and not str(record.get('name') or '').strip():
        return True
    return False


def _classify_v1(record: Mapping[str, Any], *, version: str) -> dict[str, Any]:
    out = classify_ivd(record)
    reason = out.get('reason') if isinstance(out.get('reason'), dict) else {}
    needs_review = _strict_needs_review(record=record, decision=out)
    if not isinstance(reason, dict):
        reason = {}
    reason['needs_review'] = bool(reason.get('needs_review')) or bool(needs_review)

    return {
        'is_ivd': bool(out.get('is_ivd')),
        'ivd_category': out.get('ivd_category'),
        'ivd_subtypes': out.get('ivd_subtypes') or [],
        'confidence': float(out.get('confidence', 0.5)),
        'reason': reason or {'needs_review': True},
        # Public-facing version string (human readable / canary-friendly).
        'version': str(version),
        # Internal rule engine version (int) for DB storage / comparisons.
        'rule_version': int(out.get('version') or INTERNAL_RULE_VERSION),
        'source': str(out.get('source') or 'RULE'),
    }


_SUPPORTED: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    DEFAULT_VERSION: lambda record: _classify_v1(record, version=DEFAULT_VERSION),
}


def classify(record: dict[str, Any] | Mapping[str, Any], version: str = DEFAULT_VERSION) -> dict[str, Any]:
    """Rule-first IVD classifier facade.

    - `version` is a stable, human-readable string.
    - Output includes `rule_version` (int) for existing DB schema compatibility.
    """
    ver = str(version or '').strip() or DEFAULT_VERSION
    impl = _SUPPORTED.get(ver)
    if impl is None:
        raise ValueError(f'unsupported ivd classifier version: {ver}')
    return impl(record)

