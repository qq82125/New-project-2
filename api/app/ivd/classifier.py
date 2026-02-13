from __future__ import annotations

from typing import Any

from app.services.ivd_classifier import classify_ivd


def classify(record: dict[str, Any], version: str = 'ivd_v1_20260213') -> dict[str, Any]:
    """Rule-first IVD classifier facade used by new pipeline modules.

    The internal implementation reuses the project's battle-tested classifier and
    adapts output to a stable contract required by sync/cleanup/audit flows.
    """
    out = classify_ivd(record)
    return {
        'is_ivd': bool(out.get('is_ivd')),
        'ivd_category': out.get('ivd_category'),
        'confidence': float(out.get('confidence', 0.5)),
        'reason': out.get('reason') or {'needs_review': True},
        'version': version,
        'source': str(out.get('source') or 'RULE'),
    }
