from __future__ import annotations

from datetime import date, timedelta

from app.workers import cli


def test_metrics_recompute_default_since_is_365_days(monkeypatch) -> None:
    captured = {}

    class FakeDB:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli, 'SessionLocal', lambda: FakeDB())

    def _regen(_db, *, days: int):
        captured['days'] = days
        return ['x'] * days

    monkeypatch.setattr('app.services.metrics.regenerate_daily_metrics', _regen)

    rc = cli._run_metrics_recompute(scope='ivd', since=None)  # type: ignore[attr-defined]
    assert rc == 0

    expected_days = max(1, (date.today() - (date.today() - timedelta(days=365))).days + 1)
    assert captured['days'] == expected_days
