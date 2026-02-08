from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def _cfg():
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
    )


def test_auth_me_returns_membership_and_entitlements(monkeypatch) -> None:
    user = SimpleNamespace(
        id=1,
        email='user@example.com',
        password_hash='x',
        role='user',
        plan='free',
        plan_status='inactive',
        plan_expires_at=None,
    )
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())

    client = TestClient(main.app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/auth/me')
    assert r.status_code == 200
    data = r.json()['data']
    assert data['plan'] == 'free'
    assert data['plan_status'] == 'inactive'
    assert data['entitlements']['can_export'] is False
    assert data['entitlements']['max_subscriptions'] == 3
    assert data['entitlements']['trend_range_days'] == 30


def test_export_denied_for_free_allowed_for_pro(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    free_user = SimpleNamespace(id=1, email='free@example.com', password_hash='x', role='user')
    pro_user = SimpleNamespace(
        id=2,
        email='pro@example.com',
        password_hash='x',
        role='user',
        plan='pro_annual',
        plan_status='active',
        plan_expires_at=now + timedelta(days=10),
    )

    def _get_user(_db, user_id: int):
        return {1: free_user, 2: pro_user}.get(int(user_id))

    monkeypatch.setattr('app.main.get_user_by_id', _get_user)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())
    monkeypatch.setattr('app.main.export_search_to_csv', lambda _db, **kwargs: 'a,b\n1,2\n')

    client = TestClient(main.app)

    token_free = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_free)
    r0 = client.get('/api/export/search.csv?q=x')
    assert r0.status_code == 403

    token_pro = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_pro)
    r1 = client.get('/api/export/search.csv?q=x')
    assert r1.status_code == 200
    assert 'text/csv' in (r1.headers.get('content-type') or '')
    assert 'a,b' in r1.text


def test_subscription_limit_free_3_pro_50(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    free_user = SimpleNamespace(
        id=1,
        email='free@example.com',
        password_hash='x',
        role='user',
        plan='free',
        plan_status='inactive',
        plan_expires_at=None,
    )
    pro_user = SimpleNamespace(
        id=2,
        email='pro@example.com',
        password_hash='x',
        role='user',
        plan='pro_annual',
        plan_status='active',
        plan_expires_at=now + timedelta(days=10),
    )

    def _get_user(_db, user_id: int):
        return {1: free_user, 2: pro_user}.get(int(user_id))

    monkeypatch.setattr('app.main.get_user_by_id', _get_user)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())

    # Free user already has 3 -> deny creating another.
    monkeypatch.setattr(
        'app.main.count_active_subscriptions_by_subscriber',
        lambda _db, subscriber_key: 3 if subscriber_key == free_user.email else 49,
    )

    created = {}

    def _create(_db, subscription_type: str, target_value: str, webhook_url: str | None, **kwargs):
        created['ok'] = True
        return SimpleNamespace(
            id=123,
            subscriber_key=kwargs.get('subscriber_key') or 'x',
            channel=kwargs.get('channel') or 'webhook',
            email_to=kwargs.get('email_to'),
            subscription_type=subscription_type,
            target_value=target_value,
            webhook_url=webhook_url,
            is_active=True,
            created_at=now,
        )

    monkeypatch.setattr('app.main.create_subscription', _create)

    client = TestClient(main.app)
    payload = {
        'subscription_type': 'keyword',
        'target_value': 'abc',
        'channel': 'webhook',
        'webhook_url': 'https://example.com/hook',
    }

    token_free = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_free)
    r0 = client.post('/api/subscriptions', json=payload)
    assert r0.status_code == 403

    token_pro = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_pro)
    r1 = client.post('/api/subscriptions', json=payload)
    assert r1.status_code == 200
    assert created.get('ok') is True


def test_trend_range_enforced(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    pro_user = SimpleNamespace(
        id=1,
        email='pro@example.com',
        password_hash='x',
        role='user',
        plan='pro_annual',
        plan_status='active',
        plan_expires_at=now + timedelta(days=10),
    )
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: pro_user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg())
    monkeypatch.setattr('app.main.get_trend', lambda _db, days: [])

    client = TestClient(main.app)

    # Anonymous/free: 31 days -> forbidden.
    r0 = client.get('/api/dashboard/trend?days=31')
    assert r0.status_code == 403

    # Pro: 365 days -> ok.
    token_pro = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_pro)
    r1 = client.get('/api/dashboard/trend?days=365')
    assert r1.status_code == 200

