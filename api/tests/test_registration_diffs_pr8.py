from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
import app.main as main


class _FakeExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, reg, rows):
        self._reg = reg
        self._rows = rows

    def scalar(self, _stmt):
        return self._reg

    def execute(self, _stmt):
        return _FakeExecResult(self._rows)


def test_registration_diffs_404_when_registration_missing(monkeypatch) -> None:
    monkeypatch.setattr('app.main.normalize_registration_no', lambda x: x.strip())
    fake_db = _FakeDb(reg=None, rows=[])
    app.dependency_overrides[main.get_db] = lambda: fake_db

    client = TestClient(app)
    resp = client.get('/api/registrations/CN123/diffs')
    assert resp.status_code == 404

    app.dependency_overrides.clear()


def test_registration_diffs_groups_by_snapshot_and_returns_total(monkeypatch) -> None:
    monkeypatch.setattr('app.main.normalize_registration_no', lambda x: x.strip())
    reg = SimpleNamespace(id=uuid.uuid4(), registration_no='CN-001')
    raw_id = uuid.uuid4()
    rows = [
        SimpleNamespace(
            snapshot_id=uuid.uuid4(),
            snapshot_date=date(2026, 2, 18),
            snapshot_created_at=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            snapshot_source_url='https://nmpa.example/s1',
            raw_document_id=raw_id,
            raw_source='nmpa',
            raw_source_url='https://docs.example/r1',
            raw_fetched_at=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
            field_name='status',
            old_value='ACTIVE',
            new_value='CANCELLED',
        ),
        SimpleNamespace(
            snapshot_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
            snapshot_date=date(2026, 2, 17),
            snapshot_created_at=datetime(2026, 2, 17, 9, 0, tzinfo=timezone.utc),
            snapshot_source_url='https://nmpa.example/s2',
            raw_document_id=None,
            raw_source=None,
            raw_source_url=None,
            raw_fetched_at=None,
            field_name='approval_date',
            old_value='2020-01-01',
            new_value='2020-02-01',
        ),
        SimpleNamespace(
            snapshot_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
            snapshot_date=date(2026, 2, 17),
            snapshot_created_at=datetime(2026, 2, 17, 9, 0, tzinfo=timezone.utc),
            snapshot_source_url='https://nmpa.example/s2',
            raw_document_id=None,
            raw_source=None,
            raw_source_url=None,
            raw_fetched_at=None,
            field_name='expiry_date',
            old_value='2030-01-01',
            new_value='2030-12-31',
        ),
    ]
    fake_db = _FakeDb(reg=reg, rows=rows)
    app.dependency_overrides[main.get_db] = lambda: fake_db

    client = TestClient(app)
    resp = client.get('/api/registrations/CN-001/diffs?limit=5&offset=0')
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 0
    assert body['data']['total'] == 2
    assert len(body['data']['items']) == 2
    assert body['data']['items'][0]['diffs'][0]['field'] == 'status'
    assert body['data']['items'][0]['diffs'][0]['group'] == '基本信息'
    assert body['data']['items'][0]['diffs'][0]['evidence_raw_document_id'] == str(raw_id)

    app.dependency_overrides.clear()


def test_registration_diffs_supports_limit_offset(monkeypatch) -> None:
    monkeypatch.setattr('app.main.normalize_registration_no', lambda x: x.strip())
    reg = SimpleNamespace(id=uuid.uuid4(), registration_no='CN-002')
    rows = [
        SimpleNamespace(
            snapshot_id=uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
            snapshot_date=date(2026, 2, 18),
            snapshot_created_at=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
            snapshot_source_url=None,
            raw_document_id=None,
            raw_source=None,
            raw_source_url=None,
            raw_fetched_at=None,
            field_name='status',
            old_value='ACTIVE',
            new_value='ACTIVE',
        ),
        SimpleNamespace(
            snapshot_id=uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
            snapshot_date=date(2026, 2, 17),
            snapshot_created_at=datetime(2026, 2, 17, 9, 0, tzinfo=timezone.utc),
            snapshot_source_url=None,
            raw_document_id=None,
            raw_source=None,
            raw_source_url=None,
            raw_fetched_at=None,
            field_name='track',
            old_value='A',
            new_value='B',
        ),
    ]
    fake_db = _FakeDb(reg=reg, rows=rows)
    app.dependency_overrides[main.get_db] = lambda: fake_db

    client = TestClient(app)
    resp = client.get('/api/registrations/CN-002/diffs?limit=1&offset=1')
    assert resp.status_code == 200
    body = resp.json()
    assert body['data']['total'] == 2
    assert len(body['data']['items']) == 1
    assert body['data']['items'][0]['diffs'][0]['field'] == 'track'

    app.dependency_overrides.clear()
