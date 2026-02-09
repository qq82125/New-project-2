from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        auth_secret='test-secret',
        auth_cookie_name='ivd_session',
        auth_session_ttl_hours=1,
        auth_cookie_secure=False,
        cors_origins='http://localhost:3000',
        bootstrap_admin_email='',
        bootstrap_admin_password='',
        admin_username='admin',
        admin_password='secret',
        data_sources_crypto_key='unit-test-key',
    )


def test_admin_source_runs_and_sync_run(monkeypatch) -> None:
    users = {
        1: SimpleNamespace(id=1, email='user@example.com', password_hash='x', role='user'),
        2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin'),
    }
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg())

    # source runs list
    run = SimpleNamespace(
        id=123,
        source='nmpa_udi',
        status='success',
        message='ok',
        records_total=10,
        records_success=10,
        records_failed=0,
        added_count=1,
        updated_count=2,
        removed_count=0,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr('app.main.list_source_runs', lambda _db, limit=50: [run])

    called = {'n': 0}

    def _spawn():
        called['n'] += 1

    monkeypatch.setattr('app.main._spawn_sync_thread', _spawn)

    client = TestClient(main.app)

    # non-admin forbidden
    token_user = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_user)
    r0 = client.get('/api/admin/source-runs')
    assert r0.status_code == 403
    r00 = client.post('/api/admin/sync/run')
    assert r00.status_code == 403

    # admin ok
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r1 = client.get('/api/admin/source-runs?limit=10')
    assert r1.status_code == 200
    assert r1.json()['data']['items'][0]['id'] == 123

    r2 = client.post('/api/admin/sync/run')
    assert r2.status_code == 200
    assert r2.json()['data']['queued'] is True
    assert called['n'] == 1

