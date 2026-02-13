from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
import app.main as main


def _patch_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.main.get_settings',
        lambda: SimpleNamespace(
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
        ),
    )


def test_changes_list_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))
    monkeypatch.setattr('app.main.list_recent_changes', lambda *_args, **_kwargs: [])

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/changes?days=30&limit=10')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_changes_list_allows_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='pro@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=True))

    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')
    product = SimpleNamespace(
        id=uuid.uuid4(),
        udi_di='UDI-1',
        reg_no='REG-1',
        name='Test Kit',
        status='active',
        approved_date=None,
        expiry_date=None,
        class_name='II',
        company=company,
    )
    change = SimpleNamespace(
        id=10,
        change_type='updated',
        change_date=datetime.now(timezone.utc),
        changed_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr('app.main.list_recent_changes', lambda *_args, **_kwargs: [(change, product)])

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/changes?days=30&limit=10')
    assert r.status_code == 200
    body = r.json()
    assert body['code'] == 0
    assert body['data']['items'][0]['product']['name'] == 'Test Kit'


def test_changes_stats_does_not_require_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    monkeypatch.setattr('app.main.get_change_stats', lambda *_args, **_kwargs: (3, {'new': 1, 'updated': 2}))
    client = TestClient(app)
    r = client.get('/api/changes/stats?days=30')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert r.json()['data']['total'] == 3

