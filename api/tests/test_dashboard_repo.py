from __future__ import annotations

from app.repositories.dashboard import get_trend


class FakeDB:
    def __init__(self):
        self.sql = ''

    def scalars(self, stmt):
        self.sql = str(stmt)
        return []


def test_dashboard_trend_queries_daily_metrics() -> None:
    db = FakeDB()
    _ = get_trend(db, days=30)
    assert 'daily_metrics' in db.sql
