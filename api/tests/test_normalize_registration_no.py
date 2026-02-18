from __future__ import annotations

import pytest

from app.services.normalize_keys import normalize_registration_no


@pytest.mark.parametrize(
    "inp, expected",
    [
        (" 国械注准 2023 1234 ", "国械注准20231234"),
        ("粤械备（2014）0023", "粤械备20140023"),
        ("粤械备(2014)0023", "粤械备20140023"),
        ("国械注准２０２３１２３４", "国械注准20231234"),  # full-width digits
        ("ＡＢＣ１２３", "ABC123"),  # full-width letters+digits
        ("国械注准2023-12/34", "国械注准20231234"),
        ("国械注准\t2023\n1234", "国械注准20231234"),
        ("abc-Def", "ABCDEF"),
        ("国械注准〔2023〕1234", "国械注准20231234"),
        ("粤械备【2014】0023", "粤械备20140023"),
        # UDI export sometimes concatenates multiple reg numbers into one field; keep the first segment.
        (
            "苏械注准20162220838苏械注准20152021027苏械注准20172661896",
            "苏械注准20162220838",
        ),
    ],
)
def test_normalize_registration_no_examples(inp: str, expected: str) -> None:
    assert normalize_registration_no(inp) == expected


def test_normalize_registration_no_empty_returns_none() -> None:
    assert normalize_registration_no(None) is None
    assert normalize_registration_no("") is None
    assert normalize_registration_no("   ") is None
