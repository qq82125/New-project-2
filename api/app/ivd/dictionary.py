from __future__ import annotations

# Minimal normalized ontology for rule-first v1 classifier.
IVD_POSITIVE_REAGENT = (
    '体外诊断',
    '检测试剂',
    '试剂盒',
    '校准品',
    '质控品',
    '引物探针',
)
IVD_POSITIVE_INSTRUMENT = (
    '分析仪',
    '检测仪',
    '工作站',
    '免疫分析系统',
    '生化分析仪',
    'pcr仪',
)
IVD_POSITIVE_SOFTWARE = (
    '分析软件',
    '判读软件',
    'lis',
    '检验信息系统',
    '配套软件',
)
IVD_NEGATIVE = (
    '植入',
    '治疗',
    '外科',
    '敷料',
    '缝合',
    '支架',
    '导管',
    '假体',
)
