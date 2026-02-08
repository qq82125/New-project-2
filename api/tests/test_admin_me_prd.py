from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def test_admin_me_requires_admin_role(monkeypatch) -> None:
    users: dict[int, SimpleNamespace] = {
        1: SimpleNamespace(id=1, email='user@example.com', password_hash='x', role='user'),
        2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin'),
    }

    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))

    cfg = SimpleNamespace(
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
    monkeypatch.setattr('app.main.get_settings', lambda: cfg)

    client = TestClient(main.app)

    # Not logged in.
    r0 = client.get('/api/admin/me')
    assert r0.status_code == 401

    # Logged in but not admin.
    token_user = main.create_session_token(user_id=1, secret=cfg.auth_secret, ttl_seconds=3600)
    client.cookies.set(cfg.auth_cookie_name, token_user)
    r1 = client.get('/api/admin/me')
    assert r1.status_code == 403

    # Logged in as admin.
    token_admin = main.create_session_token(user_id=2, secret=cfg.auth_secret, ttl_seconds=3600)
    client.cookies.set(cfg.auth_cookie_name, token_admin)
    r2 = client.get('/api/admin/me')
    assert r2.status_code == 200
    assert r2.json()['data']['email'] == 'admin@example.com'

