from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def test_free_subscription_limit_3_then_403(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    user = SimpleNamespace(
        id=1,
        email='user@example.com',
        password_hash='x',
        role='user',
        plan='free',
        plan_status='inactive',
        plan_expires_at=None,
        onboarded=True,
        created_at=now,
    )

    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
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

    created = []

    def _count(_db, subscriber_key: str) -> int:
        assert subscriber_key == user.email
        return len(created)

    def _create(_db, subscription_type: str, target_value: str, webhook_url: str | None, **kwargs):
        # Append first, so next call sees incremented count.
        item = SimpleNamespace(
            id=len(created) + 1,
            subscriber_key=kwargs.get('subscriber_key') or user.email,
            channel=kwargs.get('channel') or 'webhook',
            email_to=kwargs.get('email_to'),
            subscription_type=subscription_type,
            target_value=target_value,
            webhook_url=webhook_url,
            is_active=True,
            created_at=now,
        )
        created.append(item)
        return item

    monkeypatch.setattr('app.main.count_active_subscriptions_by_subscriber', _count)
    monkeypatch.setattr('app.main.create_subscription', _create)

    client = TestClient(main.app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    payload = {
        'subscription_type': 'keyword',
        'target_value': 'abc',
        'channel': 'webhook',
        'webhook_url': 'https://example.com/hook',
    }

    for _ in range(3):
        r = client.post('/api/subscriptions', json=payload)
        assert r.status_code == 200

    r4 = client.post('/api/subscriptions', json=payload)
    assert r4.status_code == 403
    body = r4.json()
    assert body['error'] == 'SUBSCRIPTION_LIMIT'
    assert 'Free' in body['message']

