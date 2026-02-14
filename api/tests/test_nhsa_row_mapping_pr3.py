from __future__ import annotations

import pytest

from app.services.nhsa_ingest import _map_nhsa_row, _normalize_month


def test_normalize_month_accepts_yyyy_mm() -> None:
    assert _normalize_month("2026-01") == "2026-01"


@pytest.mark.parametrize("bad", ["", "2026", "2026-1", "2026-13", "x2026-01", "2026-01-01"])
def test_normalize_month_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        _normalize_month(bad)


def test_map_nhsa_row_picks_common_columns() -> None:
    row = {"医保耗材编码": "A123", "产品名称": "Foo", "规格型号": "10ml", "生产企业": "Acme"}
    mapped = _map_nhsa_row(row)
    assert mapped["code"] == "A123"
    assert mapped["name"] == "Foo"
    assert mapped["spec"] == "10ml"
    assert mapped["manufacturer"] == "Acme"
    assert mapped["raw"]["医保耗材编码"] == "A123"

