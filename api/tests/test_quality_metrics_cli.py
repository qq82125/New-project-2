from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.quality_metrics import DailyQualityReport, QualityMetricEntry
from app.workers import cli


class _FakeDB:
    def close(self):
        return None

    def commit(self):
        return None


def _mock_report() -> DailyQualityReport:
    return DailyQualityReport(
        as_of=date(2026, 2, 20),
        metrics={
            "regno_parse_ok_rate": QualityMetricEntry(value=0.9, meta={"total": 10}),
            "regno_unknown_rate": QualityMetricEntry(value=0.1, meta={"total": 10}),
            "legacy_share": QualityMetricEntry(value=0.2, meta={"total": 10}),
            "diff_success_rate": QualityMetricEntry(value=0.8, meta={"success": 8, "failed": 2}),
            "udi_pending_count": QualityMetricEntry(value=12, meta={"pending_count": 12}),
            "field_evidence_coverage_rate": QualityMetricEntry(value=0.7, meta={"total_registrations": 10}),
        },
    )


def test_quality_metrics_cli_dry_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr("app.services.quality_metrics.compute_daily_quality_metrics", lambda *_a, **_k: _mock_report())

    called = {"upsert": 0}

    def _upsert(*_a, **_k):
        called["upsert"] += 1

    monkeypatch.setattr("app.services.quality_metrics.upsert_daily_quality_metrics", _upsert)

    rc = cli._run_quality_metrics_compute(SimpleNamespace(as_of="2026-02-20", execute=False))  # type: ignore[attr-defined]
    assert rc == 0
    assert called["upsert"] == 0

    out = capsys.readouterr().out
    assert '"dry_run": true' in out
    assert '"regno_parse_ok_rate"' in out


def test_quality_metrics_cli_execute_writes(monkeypatch) -> None:
    monkeypatch.setattr(cli, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr("app.services.quality_metrics.compute_daily_quality_metrics", lambda *_a, **_k: _mock_report())

    called = {"upsert": 0}

    def _upsert(*_a, **_k):
        called["upsert"] += 1

    monkeypatch.setattr("app.services.quality_metrics.upsert_daily_quality_metrics", _upsert)

    rc = cli._run_quality_metrics_compute(SimpleNamespace(as_of="2026-02-20", execute=True))  # type: ignore[attr-defined]
    assert rc == 0
    assert called["upsert"] == 1


def test_quality_metrics_cli_parser() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["metrics:quality-compute", "--as-of", "2026-02-20", "--dry-run"])
    assert args.cmd == "metrics:quality-compute"
    assert args.as_of == "2026-02-20"
    assert args.dry_run is True
