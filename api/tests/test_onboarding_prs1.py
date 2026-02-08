from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


class _DummyDB:
    def add(self, _obj):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


def test_auth_me_includes_onboarded_and_mark_onboarded(monkeypatch) -> None:
    user = SimpleNamespace(
        id=1,
        email='user@example.com',
        password_hash='x',
        role='user',
        plan='free',
        plan_status='inactive',
        plan_expires_at=None,
        onboarded=False,
    )

    def _get_db_override():
        yield _DummyDB()

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

    client = TestClient(main.app)
    main.app.dependency_overrides[main.get_db] = _get_db_override
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r0 = client.get('/api/auth/me')
    assert r0.status_code == 200
    assert r0.json()['data']['onboarded'] is False

    r1 = client.post('/api/users/onboarded')
    assert r1.status_code == 200
    assert r1.json()['data']['onboarded'] is True
    assert user.onboarded is True

    main.app.dependency_overrides.clear()
