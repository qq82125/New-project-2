from datetime import date

import pytest
from fastapi import HTTPException

from app.services import exports


class DummyUsage:
    def __init__(self, used_count: int) -> None:
        self.used_count = used_count


class DummyDB:
    pass


def test_enforce_export_quota_within_limit(monkeypatch) -> None:
    db = DummyDB()
    monkeypatch.setattr(exports, 'get_export_usage', lambda _db, _today, _plan: DummyUsage(0))
    called = {'n': 0}

    def _inc(_db, _today, _plan):
        called['n'] += 1
        return None

    monkeypatch.setattr(exports, 'increase_export_usage', _inc)
    exports.enforce_export_quota(db, 'basic')
    assert called['n'] == 1


def test_enforce_export_quota_exceeded(monkeypatch) -> None:
    db = DummyDB()
    monkeypatch.setattr(exports, 'get_export_usage', lambda _db, _today, _plan: DummyUsage(999))
    monkeypatch.setattr(exports, '_plan_limit', lambda _plan: 1)

    with pytest.raises(HTTPException) as ex:
        exports.enforce_export_quota(db, 'basic')
    assert ex.value.status_code == 429
