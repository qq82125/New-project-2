from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


class _FakeExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, raw_doc, rows):
        self._raw_doc = raw_doc
        self._rows = rows

    def get(self, _model, _id):
        return self._raw_doc

    def execute(self, _stmt):
        return _FakeExecResult(self._rows)


def test_evidence_endpoint_404_when_missing() -> None:
    app.dependency_overrides[main.get_db] = lambda: _FakeDb(raw_doc=None, rows=[])
    client = TestClient(app)
    resp = client.get(f'/api/evidence/{uuid.uuid4()}')
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_evidence_endpoint_returns_meta_and_excerpts() -> None:
    raw_id = uuid.uuid4()
    raw_doc = SimpleNamespace(
        id=raw_id,
        source='nmpa',
        source_url='https://example.com/doc',
        fetched_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
        parse_status='ok',
        run_id='run-1',
    )
    rows = [
        SimpleNamespace(
            evidence_text='片段A',
            param_code='status',
            evidence_page=1,
            registry_no='REG-001',
            observed_at=datetime(2026, 2, 20, 11, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            evidence_text='片段B',
            param_code='expiry_date',
            evidence_page=None,
            registry_no='REG-001',
            observed_at=None,
        ),
    ]
    app.dependency_overrides[main.get_db] = lambda: _FakeDb(raw_doc=raw_doc, rows=rows)

    client = TestClient(app)
    resp = client.get(f'/api/evidence/{raw_id}')
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 0
    assert body['data']['id'] == str(raw_id)
    assert body['data']['source_url'] == 'https://example.com/doc'
    assert len(body['data']['excerpts']) == 2
    assert body['data']['excerpts'][0]['field'] == 'status'
    assert body['data']['parse_meta']['parse_status'] == 'ok'

    app.dependency_overrides.clear()
