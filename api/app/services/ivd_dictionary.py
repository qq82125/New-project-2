from __future__ import annotations

# Scope allowlist for policy visibility/audit.
IVD_SCOPE_ALLOWLIST: tuple[str, ...] = ('22', '6840', '07(ivd)', '21(ivd)')

# IVD category gate dictionaries
IVD_INSTRUMENT_INCLUDE: tuple[str, ...] = (
    '分析仪',
    '检测仪',
    '测定仪',
    '扩增仪',
    '化学发光',
    '免疫分析',
    '生化',
    '血球',
    '血凝',
    'poct',
)

# Stricter set used only when class_code is missing.
IVD_INSTRUMENT_FALLBACK_INCLUDE: tuple[str, ...] = (
    '检测仪',
    '分析仪',
    '测定仪',
    '化学发光',
    '免疫分析',
    'pcr仪',
    '荧光定量',
    '核酸扩增仪',
    'poct',
)

INSTRUMENT_EXCLUDE: tuple[str, ...] = (
    '骨科',
    '口腔',
    '牙科',
    '眼科',
    '植入',
    '支架',
    '假体',
    '注射器',
)

IVD_SOFTWARE_INCLUDE: tuple[str, ...] = (
    '医疗软件',
    '诊断软件',
    '检验软件',
    '软件',
    '系统',
    '平台',
    'lis',
    '算法',
)

# Stricter set used only when class_code is missing.
IVD_SOFTWARE_FALLBACK_INCLUDE: tuple[str, ...] = (
    '诊断软件',
    '检验软件',
    '实验室信息系统',
    'lis',
    'lims',
    '辅助诊断',
    '判读软件',
)

IVD_REAGENT_INCLUDE: tuple[str, ...] = (
    '试剂',
    '试剂盒',
    '检测试剂',
    '检测试剂盒',
    '核酸检测试剂',
    '校准品',
    '质控品',
    '抗原',
    '抗体',
    '酶联免疫',
)

SOFTWARE_EXCLUDE: tuple[str, ...] = (
    '财务软件',
    '办公软件',
    '游戏',
    '娱乐',
)

# Hard excludes requested by product scope governance.
# Any hit should be treated as non-IVD even if class_code would otherwise pass.
IVD_GLOBAL_EXCLUDE: tuple[str, ...] = (
    '采血管',
    '采集容器',
    '超声影像',
    '培养箱',
    '计划软件',
    '离心机',
    '低温冰箱',
    '采血针',
    '保存箱',
    '安全柜',
    '保存管',
    '康复训练',
    '参比电极',
)

# Subtype dictionaries (applied only when is_ivd=true)
NGS_INCLUDE: tuple[str, ...] = (
    'ngs',
    '二代测序',
    '高通量测序',
    'next generation sequencing',
)

PCR_INCLUDE: tuple[str, ...] = (
    'pcr',
    'qpcr',
    'rt-pcr',
    '核酸扩增',
    '聚合酶链式反应',
)

POCT_INCLUDE: tuple[str, ...] = (
    'poct',
    '即时检验',
    '床旁检测',
    'point-of-care',
)
