from __future__ import annotations

from app.services.nmpa_assets import classify_shadow_diff_reason


def test_classify_shadow_diff_reason_codes() -> None:
    assert classify_shadow_diff_reason("missing registration field") == "FIELD_MISSING"
    assert classify_shadow_diff_reason("type mismatch for expiry_date") == "TYPE_MISMATCH"
    assert classify_shadow_diff_reason("value too long for field model") == "VALUE_TOO_LONG"
    assert classify_shadow_diff_reason("registration_no semantic parse failed") == "PARSE_ERROR"
    assert classify_shadow_diff_reason("something unexpected") == "UNKNOWN"
