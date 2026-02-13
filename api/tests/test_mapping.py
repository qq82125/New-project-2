from datetime import date, timedelta

import pytest

from app.services.ivd_scope import IVD_RULE_VERSION, classify_ivd_raw_record, is_ivd_candidate_text, is_ivd_raw_record
from app.services.mapping import diff_fields, map_raw_record, normalize_status


def test_map_raw_record_with_cn_keys_and_raw_preserved() -> None:
    raw = {
        '产品标识DI': '12345',
        '产品名称': '检测试剂盒',
        '注册人名称': '某某医疗',
        '注册证编号': '国械注准123',
        '管理类别': 'III',
    }
    record = map_raw_record(raw)
    assert record.udi_di == '12345'
    assert record.name == '检测试剂盒'
    assert record.reg_no == '国械注准123'
    assert record.class_name == 'III'
    assert record.raw == raw


def test_map_raw_record_rejects_placeholder_udi() -> None:
    raw = {
        '产品标识DI': 'IVD-f793111df8ef4cf5aa4f',
        '产品名称': '体外诊断试剂',
        '管理类别': 'III',
    }
    with pytest.raises(ValueError, match='placeholder'):
        map_raw_record(raw)


def test_diff_fields_detects_changes_with_old_new() -> None:
    before = {'name': 'A', 'status': 'active'}
    after = {'name': 'B', 'status': 'active'}
    changed = diff_fields(before, after, ('name', 'status'))
    assert changed['name'] == {'old': 'A', 'new': 'B'}
    assert 'status' not in changed


def test_normalize_status_expired() -> None:
    expiry = date.today() - timedelta(days=1)
    assert normalize_status(None, expiry) == 'expired'


def test_ivd_scope_accepts_reagent_and_software() -> None:
    assert is_ivd_candidate_text('体外诊断 试剂盒')
    assert is_ivd_candidate_text('医学检验软件系统')


def test_ivd_scope_rejects_non_ivd_device() -> None:
    raw = {'产品名称': '骨科植入假体', '管理类别': 'III'}
    assert is_ivd_raw_record(raw) is False


def test_ivd_scope_decision_contains_reason_and_version() -> None:
    decision = classify_ivd_raw_record({'产品名称': '体外诊断试剂盒', '管理类别': 'III'})
    assert decision.is_ivd is True
    assert decision.reason
    assert decision.ivd_version == IVD_RULE_VERSION
