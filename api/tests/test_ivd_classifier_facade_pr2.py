from __future__ import annotations

import pytest

from app.ivd.classifier import DEFAULT_VERSION, classify


def test_facade_unknown_version_raises() -> None:
    with pytest.raises(ValueError):
        classify({'classification_code': '22', 'name': '体外诊断试剂'}, version='ivd_v999')


def test_facade_strict_needs_review_for_uncertain_non_ivd() -> None:
    out = classify({'classification_code': '', 'name': 'Anti-C1q ELISA (IgG)'}, version=DEFAULT_VERSION)
    assert out['is_ivd'] is False
    assert out['ivd_category'] is None
    assert isinstance(out['reason'], dict)
    assert out['reason'].get('needs_review') is True


def test_facade_no_needs_review_when_class_code_present() -> None:
    out = classify({'classification_code': '07', 'name': '骨科分析仪'}, version=DEFAULT_VERSION)
    assert out['is_ivd'] is False
    assert out['reason'].get('needs_review') is False

