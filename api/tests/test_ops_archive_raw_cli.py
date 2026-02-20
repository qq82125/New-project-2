from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workers import cli


class _FakeDB:
    def close(self):
        return None


class _FakeReport:
    def as_json(self):
        return {
            "dry_run": True,
            "older_than_days": 180,
            "cutoff_at": "2026-02-20T00:00:00+00:00",
            "estimated": {"documents_count": 1, "source_records_count": 2, "total_count": 3, "documents_bytes": 10, "source_records_bytes": 20, "total_bytes": 30},
            "updated": {"documents": 0, "source_records": 0},
        }


def test_parse_older_than_days() -> None:
    from app.services.raw_archive import parse_older_than_days

    assert parse_older_than_days("180d") == 180
    assert parse_older_than_days("30") == 30
    with pytest.raises(ValueError):
        parse_older_than_days("0d")
    with pytest.raises(ValueError):
        parse_older_than_days("abc")


def test_ops_archive_raw_cli_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "SessionLocal", lambda: _FakeDB())
    called = {"days": None, "dry_run": None}

    def _fake_archive(_db, *, older_than_days: int, dry_run: bool):
        called["days"] = older_than_days
        called["dry_run"] = dry_run
        return _FakeReport()

    monkeypatch.setattr("app.services.raw_archive.archive_raw_data", _fake_archive)

    rc = cli._run_ops_archive_raw(SimpleNamespace(older_than="180d", execute=False))  # type: ignore[attr-defined]
    assert rc == 0
    assert called["days"] == 180
    assert called["dry_run"] is True
    out = capsys.readouterr().out
    assert '"total_count": 3' in out


def test_ops_archive_parser() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["ops:archive-raw", "--older-than", "180d", "--dry-run"])
    assert args.cmd == "ops:archive-raw"
    assert args.older_than == "180d"
    assert args.dry_run is True
