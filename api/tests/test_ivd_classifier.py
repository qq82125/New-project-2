from __future__ import annotations

import pytest

from app.services.ivd_classifier import VERSION, classify_ivd


@pytest.mark.parametrize(
    'payload,expected_is_ivd,expected_category',
    [
        ({'classification_code': '2201', 'name': '体外诊断试剂'}, True, 'reagent'),
        ({'classification_code': '22', 'name': '任意名称'}, True, 'reagent'),
        ({'classification_code': '2202', 'name': '校准品'}, True, 'reagent'),
        ({'classification_code': '2203', 'name': '质控品'}, True, 'reagent'),
        ({'classification_code': '2299', 'name': '其他'}, True, 'reagent'),
        ({'classification_code': '2201A', 'name': '试剂盒'}, True, 'reagent'),
        ({'classification_code': '2201-xx', 'name': 'PCR 试剂'}, True, 'reagent'),
        ({'classification_code': '22XYZ', 'name': '核酸检测试剂'}, True, 'reagent'),
        ({'classification_code': '2208', 'name': '免疫检测试剂'}, True, 'reagent'),
        ({'classification_code': '2209', 'name': '生化检测试剂'}, True, 'reagent'),
        ({'classification_code': '6840', 'name': '体外诊断试剂'}, True, 'reagent'),
        ({'classification_code': '0701', 'name': '全自动生化分析仪'}, True, 'instrument'),
        ({'classification_code': '07', 'name': '血球分析仪'}, True, 'instrument'),
        ({'classification_code': '0702', 'name': '免疫分析系统'}, True, 'instrument'),
        ({'classification_code': '0703', 'name': '化学发光检测仪'}, True, 'instrument'),
        ({'classification_code': '0704', 'name': 'POCT检测仪'}, True, 'instrument'),
        ({'classification_code': '0705', 'name': '凝血测定仪'}, True, 'instrument'),
        ({'classification_code': '0706', 'name': '生化测定仪'}, True, 'instrument'),
        ({'classification_code': '0707', 'name': '骨科分析仪'}, False, None),
        ({'classification_code': '0708', 'name': '口腔检测仪'}, False, None),
        ({'classification_code': '0709', 'name': '眼科测定仪'}, False, None),
        ({'classification_code': '0710', 'name': '植入式检测仪'}, False, None),
        ({'classification_code': '0711', 'name': '支架分析仪'}, False, None),
        ({'classification_code': '0712', 'name': '普通手术器械'}, False, None),
        ({'classification_code': '0713', 'name': '影像工作站'}, False, None),
        ({'classification_code': '22', 'name': '一次性采血管'}, False, None),
        ({'classification_code': '07', 'name': '医用离心机'}, False, None),
        ({'classification_code': '21', 'name': '超声影像计划软件'}, False, None),
        ({'classification_code': '2101', 'name': '医学检验软件'}, True, 'software'),
        ({'classification_code': '21', 'name': 'LIS系统'}, True, 'software'),
        ({'classification_code': '2102', 'name': '检验信息平台'}, True, 'software'),
        ({'classification_code': '2103', 'name': '诊断算法软件'}, True, 'software'),
        ({'classification_code': '2104', 'name': '辅助判读系统'}, True, 'software'),
        ({'classification_code': '2105', 'name': '医院收费软件'}, True, 'software'),
        ({'classification_code': '2106', 'name': '普通办公软件'}, False, None),
        ({'classification_code': '2107', 'name': '娱乐游戏软件'}, False, None),
        ({'classification_code': '0901', 'name': '生化分析仪'}, False, None),
        ({'classification_code': '1101', 'name': '医学检验软件'}, False, None),
        ({'classification_code': '', 'name': '乙肝检测试剂盒'}, True, 'reagent'),
        ({'classification_code': '', 'name': '实验室信息系统(LIS)'}, True, 'software'),
        ({'classification_code': '', 'name': 'Anti-C1q ELISA (IgG)'}, False, None),
        ({'class_code': '22AA', 'name': '兼容字段测试'}, True, 'reagent'),
    ],
)
def test_classify_ivd_v1_cases(payload, expected_is_ivd, expected_category) -> None:
    result = classify_ivd(payload)
    assert result['is_ivd'] is expected_is_ivd
    assert result['ivd_category'] == expected_category
    assert result['version'] == VERSION
    assert isinstance(result['reason'], dict)
    assert 'ivd' in result['reason']
    assert 'subtypes' in result['reason']


def test_classify_ivd_07_edge_case_non_ivd_reason() -> None:
    result = classify_ivd({'classification_code': '07', 'name': '普通输液器'})
    assert result['is_ivd'] is False
    assert result['ivd_category'] is None
    assert result['reason']['ivd']['code'] == '07'
    assert result['reason']['ivd']['category'] is None
    assert result['version'] == VERSION


def test_classify_ivd_21_edge_case_non_ivd_reason() -> None:
    result = classify_ivd({'classification_code': '21', 'name': '普通办公软件'})
    assert result['is_ivd'] is False
    assert result['ivd_category'] is None
    assert result['reason']['ivd']['code'] == '21'
    assert result['reason']['ivd']['category'] is None
    assert result['version'] == VERSION


@pytest.mark.parametrize(
    'name,expected_subtypes',
    [
        ('二代测序分析系统', {'NGS'}),
        ('高通量测序与核酸扩增分析平台', {'NGS', 'PCR'}),
        ('RT-PCR核酸扩增检测试剂', {'PCR'}),
        ('POCT即时检验设备', {'POCT'}),
        ('Point-of-care qPCR检测系统', {'POCT', 'PCR'}),
        ('常规体外诊断试剂', set()),
    ],
)
def test_subtype_tags_only_for_ivd(name: str, expected_subtypes: set[str]) -> None:
    result = classify_ivd({'classification_code': '22', 'name': name})
    assert result['is_ivd'] is True
    assert set(result['ivd_subtypes']) == expected_subtypes
    subtype_types = {item['type'] for item in result['reason']['subtypes']}
    assert subtype_types == expected_subtypes


def test_subtype_not_applied_for_non_ivd_even_when_keyword_hit() -> None:
    result = classify_ivd({'classification_code': '09', 'name': 'RT-PCR设备'})
    assert result['is_ivd'] is False
    assert result['ivd_subtypes'] == []
    assert result['reason']['subtypes'] == []


@pytest.mark.parametrize(
    'name,expected_hit',
    [
        ('一次性采血管', '采血管'),
        ('医用采集容器', '采集容器'),
        ('超声影像工作站', '超声影像'),
        ('二氧化碳培养箱', '培养箱'),
        ('检验计划软件', '计划软件'),
        ('低速离心机', '离心机'),
        ('医用低温冰箱', '低温冰箱'),
        ('采血针', '采血针'),
        ('样本保存箱', '保存箱'),
        ('生物安全柜', '安全柜'),
        ('样本保存管', '保存管'),
        ('康复训练系统', '康复训练'),
        ('参比电极', '参比电极'),
    ],
)
def test_global_exclude_keywords_force_non_ivd(name: str, expected_hit: str) -> None:
    result = classify_ivd({'classification_code': '22', 'name': name})
    assert result['is_ivd'] is False
    assert result['ivd_category'] is None
    assert result['reason']['ivd']['by'] == 'global_exclude'
    assert expected_hit in result['reason']['ivd']['exclude_hits']
