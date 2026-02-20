from __future__ import annotations

import pytest

from app.services.registration_no_parser import parse_registration_no


def test_parse_new_registration_number() -> None:
    parsed = parse_registration_no("国械注准20243220123")
    assert parsed.parse_ok is True
    assert parsed.parse_level == "FULL"
    assert parsed.parse_reason == "NEW_CERT_FULL"
    assert parsed.regno_type == "registration"
    assert parsed.origin_type == "domestic"
    assert parsed.approval_level == "national"
    assert parsed.management_class == 3
    assert parsed.first_year == 2024
    assert parsed.category_code == "22"
    assert parsed.serial_no == "0123"
    assert parsed.is_legacy_format is False


def test_parse_filing_number() -> None:
    parsed = parse_registration_no("沪械备202400123")
    assert parsed.parse_ok is True
    assert parsed.parse_level == "FULL"
    assert parsed.regno_type == "filing"
    assert parsed.origin_type == "filing"
    assert parsed.approval_level == "provincial"
    assert parsed.management_class is None
    assert parsed.first_year == 2024
    assert parsed.category_code is None
    assert parsed.serial_no == "00123"
    assert parsed.is_legacy_format is False


def test_parse_legacy_food_drug_supervision_variant_with_suffix() -> None:
    parsed = parse_registration_no("国食药监械许字2008第3220032号更")
    assert parsed.parse_ok is True
    assert parsed.parse_level in {"FULL", "PARTIAL"}
    assert parsed.parse_reason == "LEGACY_ACTION_SUFFIX"
    assert parsed.action_suffix == "更"
    assert parsed.regno_type == "registration"
    assert parsed.origin_type == "permit"
    assert parsed.approval_level == "national"
    assert parsed.management_class == 3
    assert parsed.first_year == 2008
    assert parsed.category_code == "322"
    assert parsed.serial_no == "0032"
    assert parsed.is_legacy_format is True


@pytest.mark.parametrize("suffix", ["更", "延", "补"])
def test_parse_legacy_action_suffixes(suffix: str) -> None:
    parsed = parse_registration_no(f"国食药监械准字2008第3450116号({suffix})")
    assert parsed.parse_ok is True
    assert parsed.parse_level in {"FULL", "PARTIAL", "CLASSIFIED"}
    assert parsed.parse_reason in {"LEGACY_ACTION_SUFFIX", "OLD_PATTERN_CLASSIFIED", "LEGACY_VARIANT"}
    assert parsed.action_suffix == suffix


def test_parse_legacy_drug_admin_variant() -> None:
    parsed = parse_registration_no("国食药管械准字2008第2400149号")
    assert parsed.parse_ok is True
    assert parsed.parse_level in {"FULL", "PARTIAL"}
    assert parsed.parse_reason in {"ISSUER_ALIAS", "LEGACY_VARIANT_FULL", "LEGACY_VARIANT"}
    assert parsed.regno_type == "registration"
    assert parsed.origin_type == "domestic"
    assert parsed.approval_level == "national"
    assert parsed.management_class == 2
    assert parsed.first_year == 2008
    assert parsed.category_code == "240"
    assert parsed.serial_no == "0149"
    assert parsed.is_legacy_format is True


def test_parse_old_pattern_classified() -> None:
    parsed = parse_registration_no("国药监械字第ABC号")
    assert parsed.parse_ok is True
    assert parsed.parse_level == "CLASSIFIED"
    assert parsed.parse_reason in {"OLD_PATTERN_CLASSIFIED", "LEGACY_VARIANT"}


def test_parse_failed_returns_unknown() -> None:
    parsed = parse_registration_no("随机无效编号")
    assert parsed.parse_ok is False
    assert parsed.parse_level == "FAIL"
    assert parsed.parse_reason == "UNKNOWN_PATTERN"
    assert parsed.regno_type == "unknown"
