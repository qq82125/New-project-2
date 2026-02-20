from __future__ import annotations

from app.services.offline_import import _normalize_row_payload, _reason_code_from_payload


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
