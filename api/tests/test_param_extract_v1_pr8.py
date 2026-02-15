from __future__ import annotations

from app.ivd.param_extract import extract_from_text, normalize_units


def test_normalize_units_cn_and_symbols() -> None:
    assert normalize_units("小时") == "h"
    assert normalize_units("分钟") == "min"
    assert normalize_units("℃") == "C"
    assert normalize_units("copies/ml") == "copies/mL"
    assert normalize_units("ng/ml") == "ng/mL"


def test_extract_from_text_range_and_percent() -> None:
    txt = """
    检出限（LOD） 1.0-5.0 ng/mL
    灵敏度 95%
    贮存条件 2-8℃ 避光保存
    """
    items = extract_from_text(txt)
    codes = {x["param_code"] for x in items}
    assert "LOD" in codes
    assert "SENSITIVITY" in codes
    assert "STORAGE_CONDITION" in codes

    lod = [x for x in items if x["param_code"] == "LOD"][0]
    assert lod["range_low"] == 1.0
    assert lod["range_high"] == 5.0
    assert lod["unit"] == "ng/mL"

    sens = [x for x in items if x["param_code"] == "SENSITIVITY"][0]
    assert sens["value_num"] == 95.0
    assert sens["unit"] == "%"

