from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def test_admin_users_requires_admin(monkeypatch) -> None:
    users = {
        1: SimpleNamespace(id=1, email='user@example.com', password_hash='x', role='user', created_at=datetime.now(timezone.utc)),
        2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin', created_at=datetime.now(timezone.utc)),
    }
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(int(user_id)))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())
    monkeypatch.setattr('app.main.admin_list_users', lambda _db, query=None, limit=50, offset=0: list(users.values()))

    client = TestClient(main.app)

    token_user = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_user)
    r0 = client.get('/api/admin/users')
    assert r0.status_code == 403

    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)
    r1 = client.get('/api/admin/users?query=user&limit=10&offset=0')
    assert r1.status_code == 200
    assert len(r1.json()['data']['items']) >= 2


def test_membership_grant_extend_suspend_revoke_routes(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    admin = SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin', created_at=now)
    target = SimpleNamespace(
        id=1,
        email='user@example.com',
        password_hash='x',
        role='user',
        plan='free',
        plan_status='inactive',
        plan_expires_at=None,
        created_at=now,
    )

    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: admin if int(user_id) == 2 else target)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())

    def _grant(_db, **kwargs):
        target.plan = 'pro_annual'
        target.plan_status = 'active'
        target.plan_expires_at = now + timedelta(days=365)
        return target

    def _extend(_db, **kwargs):
        target.plan = 'pro_annual'
        target.plan_status = 'active'
        target.plan_expires_at = (target.plan_expires_at or now) + timedelta(days=30)
        return target

    def _suspend(_db, **kwargs):
        target.plan_status = 'suspended'
        return target

    def _revoke(_db, **kwargs):
        target.plan = 'free'
        target.plan_status = 'inactive'
        target.plan_expires_at = None
        return target

    monkeypatch.setattr('app.main.admin_grant_membership', _grant)
    monkeypatch.setattr('app.main.admin_extend_membership', _extend)
    monkeypatch.setattr('app.main.admin_suspend_membership', _suspend)
    monkeypatch.setattr('app.main.admin_revoke_membership', _revoke)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r0 = client.post('/api/admin/membership/grant', json={'user_id': 1, 'plan': 'pro_annual', 'months': 12})
    assert r0.status_code == 200
    assert r0.json()['data']['plan'] == 'pro_annual'
    assert r0.json()['data']['plan_status'] == 'active'

    r1 = client.post('/api/admin/membership/extend', json={'user_id': 1, 'months': 1})
    assert r1.status_code == 200
    assert r1.json()['data']['plan'] == 'pro_annual'

    r2 = client.post('/api/admin/membership/suspend', json={'user_id': 1})
    assert r2.status_code == 200
    assert r2.json()['data']['plan_status'] == 'suspended'

    r3 = client.post('/api/admin/membership/revoke', json={'user_id': 1})
    assert r3.status_code == 200
    assert r3.json()['data']['plan'] == 'free'
    assert r3.json()['data']['plan_status'] == 'inactive'


def test_membership_grant_when_already_active_returns_409(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    admin = SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin', created_at=now)
    user = SimpleNamespace(
        id=1,
        email='user@example.com',
        password_hash='x',
        role='user',
        plan='pro_annual',
        plan_status='active',
        plan_expires_at=now + timedelta(days=10),
        created_at=now,
    )

    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: admin if int(user_id) == 2 else user)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())

    def _grant(_db, **_kwargs):
        raise ValueError('already_active_pro')

    monkeypatch.setattr('app.main.admin_grant_membership', _grant)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r = client.post('/api/admin/membership/grant', json={'user_id': 1, 'plan': 'pro_annual', 'months': 12})
    assert r.status_code == 409
