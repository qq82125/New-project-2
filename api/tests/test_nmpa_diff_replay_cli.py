from __future__ import annotations

from types import SimpleNamespace

from app.services.nmpa_assets import ShadowDiffReplayReport
from app.workers import cli


class _FakeDB:
    def close(self):
        return None


def test_nmpa_diff_replay_cli_outputs_metrics(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "SessionLocal", lambda: _FakeDB())

    def _fake_replay(_db, *, source_run_id: int, dry_run: bool):
        assert source_run_id == 77
        assert dry_run is True
        return ShadowDiffReplayReport(
            source_run_id=source_run_id,
            dry_run=dry_run,
            total_records=10,
            diff_success=8,
            diff_failed=2,
            diffs_written=14,
            reason_counts={"PARSE_ERROR": 1, "FIELD_MISSING": 1},
        )

    monkeypatch.setattr("app.services.nmpa_assets.replay_nmpa_snapshot_diffs_for_source_run", _fake_replay)

    rc = cli._run_nmpa_diff_replay(SimpleNamespace(source_run_id=77, execute=False))  # type: ignore[attr-defined]
    assert rc == 0

    out = capsys.readouterr().out
    assert '"diff_success_rate": 0.8' in out
    assert '"top_reason_codes": [{"reason_code": "FIELD_MISSING", "count": 1}, {"reason_code": "PARSE_ERROR", "count": 1}]' in out


def test_nmpa_diff_replay_parser_accepts_command() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["nmpa:diff-replay", "--source-run-id", "12", "--dry-run"])
    assert args.cmd == "nmpa:diff-replay"
    assert args.source_run_id == 12
    assert args.dry_run is True
