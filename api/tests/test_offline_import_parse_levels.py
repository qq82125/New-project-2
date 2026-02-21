from __future__ import annotations

from app.services.offline_import import (
    _extract_country_or_region,
    _normalize_row_payload,
    _origin_bucket_from_payload,
    _reason_code_from_payload,
)


def test_offline_payload_includes_parse_meta_for_legacy_variant() -> None:
    row = {"注册证号": "国食药监械准字2008第3450116号(更)", "产品名称": "test"}
    payload = _normalize_row_payload(
        row,
        source_key="nmpa_legacy_dump",
        dataset_version="dv1",
        file_sha256="abc",
        row_index=1,
    )
    assert payload["registration_no_raw"] == "国食药监械准字2008第3450116号(更)"
    assert payload["registration_no_norm"]
    assert payload["regno_parse_level"] in {"FULL", "PARTIAL", "CLASSIFIED"}
    assert payload["regno_parse_reason"]
    assert isinstance(payload["regno_parse_confidence"], float)
    assert _reason_code_from_payload(payload) == "OK"


def test_offline_payload_missing_regno_marks_fail_reason() -> None:
    row = {"产品名称": "test"}
    payload = _normalize_row_payload(
        row,
        source_key="nmpa_legacy_dump",
        dataset_version="dv1",
        file_sha256="abc",
        row_index=1,
    )
    assert payload["registration_no_raw"] is None
    assert payload["regno_parse_level"] == "FAIL"
    assert payload["regno_parse_reason"] == "REGNO_MISSING"
    assert _reason_code_from_payload(payload) == "REGNO_MISSING"


def test_country_region_extract_prefers_production_address() -> None:
    row = {
        "注册人住所": "日本东京都文京区本乡三丁目27番20号",
        "生产地址": "Fabrikstrasse 31, Bensheim 64625, Germany",
    }
    res = _extract_country_or_region(row)
    assert res is not None
    assert res.country_or_region == "德国"
    assert res.geo_type == "country"
    assert res.source_field == "生产地址"


def test_country_region_extract_supports_region_label() -> None:
    row = {"生产地址": "中国香港沙田区XX路1号"}
    res = _extract_country_or_region(row)
    assert res is not None
    assert res.country_or_region == "中国香港"
    assert res.geo_type == "region"


def test_origin_bucket_from_payload() -> None:
    payload = {
        "registration_no_norm": "国械注进20243220123",
    }
    assert _origin_bucket_from_payload(payload) == "import"
