from datetime import date, timedelta

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


def test_diff_fields_detects_changes_with_old_new() -> None:
    before = {'name': 'A', 'status': 'active'}
    after = {'name': 'B', 'status': 'active'}
    changed = diff_fields(before, after, ('name', 'status'))
    assert changed['name'] == {'old': 'A', 'new': 'B'}
    assert 'status' not in changed


def test_normalize_status_expired() -> None:
    expiry = date.today() - timedelta(days=1)
    assert normalize_status(None, expiry) == 'expired'
