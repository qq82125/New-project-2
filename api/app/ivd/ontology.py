from __future__ import annotations

PARAM_ONTOLOGY: dict[str, dict[str, object]] = {
    # Analytical performance
    'LOD': {'aliases': ['检出限', '检测限', '最低检出浓度', 'lod', 'limit of detection'], 'units': ['copies/mL', 'copies/ml', 'ng/mL', 'ng/ml', 'IU/mL', 'iu/ml', 'U/mL', 'cfu/mL', 'g/L', 'mg/L', 'ug/mL', 'μg/mL']},
    'LOQ': {'aliases': ['定量限', 'loq', 'limit of quantitation', 'limit of quantification'], 'units': ['copies/mL', 'copies/ml', 'ng/mL', 'ng/ml', 'IU/mL', 'iu/ml', 'U/mL']},
    'SENSITIVITY': {'aliases': ['灵敏度', '敏感性', 'sensitivity'], 'units': ['%']},
    'SPECIFICITY': {'aliases': ['特异性', 'specificity'], 'units': ['%']},
    'LINEAR_RANGE': {'aliases': ['线性范围', 'linear range'], 'units': ['copies/mL', 'copies/ml', 'ng/mL', 'ng/ml', 'IU/mL', 'iu/ml', 'U/mL']},
    'MEASUREMENT_RANGE': {'aliases': ['测量范围', '可报告范围', 'reportable range', 'measuring range'], 'units': ['copies/mL', 'copies/ml', 'ng/mL', 'ng/ml', 'IU/mL', 'iu/ml', 'U/mL']},
    'REPEATABILITY': {'aliases': ['重复性', 'repeatability', '批内精密度', '批内'], 'units': ['%']},
    'REPRODUCIBILITY': {'aliases': ['再现性', 'reproducibility', '批间精密度', '批间'], 'units': ['%']},
    'CV': {'aliases': ['变异系数', 'cv', 'coefficient of variation'], 'units': ['%']},

    # Sample / workflow
    'SAMPLE_TYPE': {'aliases': ['样本类型', '样本要求', 'sample type', 'specimen'], 'units': []},
    'SAMPLE_VOLUME': {'aliases': ['样本量', '加样量', '取样量', 'sample volume'], 'units': ['uL', 'μL', 'ul', 'mL', 'ml']},
    'TURNAROUND_TIME': {'aliases': ['检测时间', '检测时长', '检测用时', 'turnaround time'], 'units': ['min', 'h', 'day']},

    # Storage / stability
    'STORAGE_CONDITION': {'aliases': ['储存条件', '贮存条件', 'storage condition'], 'units': ['C']},
    'TRANSPORT_CONDITION': {'aliases': ['运输条件', '运输温度', 'transport'], 'units': ['C']},
    'SHELF_LIFE': {'aliases': ['有效期', '保质期', 'shelf life'], 'units': ['day', 'month', 'year']},
    'OPEN_STABILITY': {'aliases': ['开封稳定性', '开瓶稳定性', '开封后稳定性', 'on-board stability'], 'units': ['day', 'h']},

    # Interference / cross-reactivity
    'INTERFERENCE': {'aliases': ['干扰', '干扰物质', 'interference'], 'units': []},
    'CROSS_REACTIVITY': {'aliases': ['交叉反应', '交叉反应性', 'cross-reactivity', 'cross reactivity'], 'units': ['%']},
}
