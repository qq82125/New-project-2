from __future__ import annotations

PARAM_ONTOLOGY: dict[str, dict[str, object]] = {
    'LOD': {'aliases': ['检出限', '检测限', '最低检出浓度', 'lod'], 'units': ['copies/mL', 'ng/mL', 'IU/mL']},
    'SENSITIVITY': {'aliases': ['灵敏度'], 'units': ['%']},
    'SPECIFICITY': {'aliases': ['特异性'], 'units': ['%']},
    'LINEAR_RANGE': {'aliases': ['线性范围'], 'units': ['copies/mL', 'ng/mL', 'IU/mL']},
    'SAMPLE_TYPE': {'aliases': ['样本类型', '样本要求'], 'units': []},
    'TURNAROUND_TIME': {'aliases': ['检测时间', '检测时长'], 'units': ['min', 'h']},
    'STORAGE_CONDITION': {'aliases': ['储存条件', '贮存条件'], 'units': []},
    'SHELF_LIFE': {'aliases': ['有效期', '保质期'], 'units': ['month', '年']},
}
