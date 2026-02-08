from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

from app.services import metrics


@dataclass
class FakeInsert:
    values_data: dict

    def on_conflict_do_update(self, index_elements, set_):
        self.set_data = set_
        return self


class FakeInsertBuilder:
    def values(self, **kwargs):
        return FakeInsert(values_data=kwargs)


class FakeDB:
    def __init__(self):
        self.rows = {}

    def execute(self, stmt):
        key = stmt.values_data['metric_date']
        existing = self.rows.get(key)
        if existing:
            for k, v in stmt.set_data.items():
                setattr(existing, k, v)
        else:
            self.rows[key] = SimpleNamespace(**stmt.values_data)

    def commit(self):
        return None

    def get(self, _model, key):
        return self.rows.get(key)


def test_generate_daily_metrics_is_rerunnable_one_row_per_day(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(metrics, 'insert', lambda _model: FakeInsertBuilder())

    seq = {'n': 0}

    def _count_change_type(_db, _day, _type):
        seq['n'] += 1
        return seq['n']

    monkeypatch.setattr(metrics, '_count_change_type', _count_change_type)
    monkeypatch.setattr(metrics, '_count_expiring_in_90d', lambda *_: 7)
    monkeypatch.setattr(metrics, '_count_active_subscriptions', lambda *_: 3)
    monkeypatch.setattr(metrics, '_latest_source_run_id', lambda *_: 99)

    target_day = date(2026, 2, 8)
    row1 = metrics.generate_daily_metrics(db, target_day)
    row2 = metrics.generate_daily_metrics(db, target_day)

    assert row1.metric_date == target_day
    assert row2.metric_date == target_day
    assert len(db.rows) == 1
