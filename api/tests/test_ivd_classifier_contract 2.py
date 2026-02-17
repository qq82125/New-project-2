from __future__ import annotations

from app.ivd.classifier import classify


def test_ivd_classifier_contract_fields() -> None:
    out = classify({'classification_code': '22', 'name': '体外诊断试剂盒'})
    assert out['is_ivd'] is True
    assert out['ivd_category'] == 'reagent'
    assert isinstance(out['confidence'], float)
    assert out['source'] == 'RULE'
    assert isinstance(out['reason'], dict)
    assert out['version'] == 'ivd_v1_20260213'
