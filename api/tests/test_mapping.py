from app.services.mapping import diff_fields, map_raw_record


def test_map_raw_record_with_cn_keys() -> None:
    raw = {
        '产品标识DI': '12345',
        '产品名称': '检测试剂盒',
        '型号': 'A1',
        '规格': '10T',
        '注册人名称': '某某医疗',
        '注册证编号': '国械注准123',
    }
    record = map_raw_record(raw)
    assert record.udi_di == '12345'
    assert record.product_name == '检测试剂盒'
    assert record.model == 'A1'
    assert record.registration_no == '国械注准123'


def test_diff_fields_detects_changes() -> None:
    before = {'name': 'A', 'model': '1'}
    after = {'name': 'B', 'model': '1'}
    changed = diff_fields(before, after, ('name', 'model'))
    assert 'name' in changed
    assert 'model' not in changed
