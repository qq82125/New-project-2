from __future__ import annotations

from pathlib import Path

from app.services.offline_import import _parse_patterns, _scan_files


def test_scan_files_recursive_depth_with_cn_paths(tmp_path: Path) -> None:
    root = tmp_path / "nmpa_legacy"
    root.mkdir()
    d2020 = root / "2020"
    d2020.mkdir()
    (d2020 / "a.xlsx").write_text("x", encoding="utf-8")
    old = d2020 / "old 数据"
    old.mkdir()
    (old / "b.csv").write_text("k,v\n1,2\n", encoding="utf-8")

    files_depth_2 = _scan_files(root, recursive=True, max_depth=2)
    rel_2 = [p.relative_to(root).as_posix() for p in files_depth_2]
    assert "2020/a.xlsx" in rel_2
    assert "2020/old 数据/b.csv" in rel_2

    files_depth_3 = _scan_files(root, recursive=True, max_depth=3)
    rel_3 = [p.relative_to(root).as_posix() for p in files_depth_3]
    assert "2020/a.xlsx" in rel_3
    assert "2020/old 数据/b.csv" in rel_3


def test_scan_files_non_recursive(tmp_path: Path) -> None:
    root = tmp_path / "nmpa_legacy"
    root.mkdir()
    (root / "x.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    sub = root / "sub"
    sub.mkdir()
    (sub / "y.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    out = _scan_files(root, recursive=False, max_depth=0)
    assert [p.name for p in out] == ["x.csv"]


def test_parse_patterns_default() -> None:
    out = _parse_patterns("*.csv,*.xlsx,*.xls,*.json,*.ndjson")
    assert out == ["*.csv", "*.xlsx", "*.xls", "*.json", "*.ndjson"]
