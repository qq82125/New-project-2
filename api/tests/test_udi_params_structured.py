from __future__ import annotations

from app.services.udi_params_structured import (
    normalize_brand,
    normalize_mjfs,
    parse_packing_json,
    parse_storage_json,
)


def test_parse_storage_json_extracts_temperatures_and_note() -> None:
    raw = [
        {"type": "储存温度", "min": 2, "max": 8, "unit": "℃", "range": "2~8℃"},
        {"type": "运输温度", "min": -20, "max": 25, "unit": "℃", "range": "-20~25℃"},
    ]
    out = parse_storage_json(raw)
    assert out["STORAGE_TEMP_MIN_C"] == 2.0
    assert out["STORAGE_TEMP_MAX_C"] == 8.0
    assert out["TRANSPORT_TEMP_MIN_C"] == -20.0
    assert out["TRANSPORT_TEMP_MAX_C"] == 25.0
    assert "2~8℃" in str(out["STORAGE_NOTE"])


def test_parse_storage_json_extracts_root_transport_fields() -> None:
    raw = {
        "storageMin": 2,
        "storageMax": 8,
        "transportMin": -20,
        "transportMax": 25,
        "note": "冷链运输",
    }
    out = parse_storage_json(raw)
    assert out["STORAGE_TEMP_MIN_C"] == 2.0
    assert out["STORAGE_TEMP_MAX_C"] == 8.0
    assert out["TRANSPORT_TEMP_MIN_C"] == -20.0
    assert out["TRANSPORT_TEMP_MAX_C"] == 25.0


def test_parse_storage_json_transport_hint_fallback() -> None:
    raw = [{"type": "贮存/运输条件", "range": "2-8℃"}]
    out = parse_storage_json(raw)
    assert out["STORAGE_TEMP_MIN_C"] == 2.0
    assert out["STORAGE_TEMP_MAX_C"] == 8.0
    assert out["TRANSPORT_TEMP_MIN_C"] == 2.0
    assert out["TRANSPORT_TEMP_MAX_C"] == 8.0


def test_parse_packing_json_prefers_primary_and_qty() -> None:
    raw = [
        {"package_level": "箱", "contains_qty": 96, "package_unit": "盒"},
        {"package_level": "盒", "contains_qty": 1, "package_unit": "袋"},
    ]
    out = parse_packing_json(raw)
    assert out["PACKAGE_LEVEL"] == "盒"
    assert out["PACKAGE_UNIT"] == "袋"
    assert out["PACKAGE_QTY"] == "1"


def test_normalize_mjfs_and_brand() -> None:
    assert normalize_mjfs(" 环氧乙烷灭菌 ") == "EO"
    assert normalize_brand(" / ACME-BRAND ; ") == "ACME-BRAND"
