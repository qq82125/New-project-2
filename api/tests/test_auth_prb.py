from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def test_auth_register_login_logout_me(monkeypatch) -> None:
    users: dict[int, SimpleNamespace] = {}
    email_index: dict[str, int] = {}
    next_id = {'value': 1}

    def get_user_by_email(_db, email: str):
        uid = email_index.get(email)
        return users.get(uid) if uid else None

    def get_user_by_id(_db, user_id: int):
        return users.get(user_id)

    def create_user(_db, email: str, password_hash: str, role: str = 'user'):
        uid = next_id['value']
        next_id['value'] += 1
        user = SimpleNamespace(id=uid, email=email, password_hash=password_hash, role=role)
        users[uid] = user
        email_index[email] = uid
        return user

    monkeypatch.setattr('app.main.get_user_by_email', get_user_by_email)
    monkeypatch.setattr('app.main.get_user_by_id', get_user_by_id)
    monkeypatch.setattr('app.main.create_user', create_user)
    monkeypatch.setattr('app.main.hash_password', lambda p: f'hash:{p}')
    monkeypatch.setattr('app.main.verify_password', lambda p, h: h == f'hash:{p}')

    cfg = SimpleNamespace(
        auth_secret='test-secret',
        auth_cookie_name='ivd_session',
        auth_session_ttl_hours=1,
        auth_cookie_secure=False,
        cors_origins='http://localhost:3000',
        bootstrap_admin_email='admin@example.com',
        bootstrap_admin_password='pass12345',
        admin_username='admin',
        admin_password='secret',
    )
    monkeypatch.setattr('app.main.get_settings', lambda: cfg)

    client = TestClient(main.app)

    register_resp = client.post(
        '/api/auth/register',
        json={'email': 'user@example.com', 'password': 'pass12345'},
    )
    assert register_resp.status_code == 200
    assert register_resp.json()['data']['email'] == 'user@example.com'
    assert cfg.auth_cookie_name in client.cookies

    me_resp = client.get('/api/auth/me')
    assert me_resp.status_code == 200
    assert me_resp.json()['data']['email'] == 'user@example.com'

    logout_resp = client.post('/api/auth/logout')
    assert logout_resp.status_code == 200
    assert logout_resp.json()['data']['logged_out'] is True
    assert cfg.auth_cookie_name not in client.cookies

    me_after_logout = client.get('/api/auth/me')
    assert me_after_logout.status_code == 401

    login_resp = client.post(
        '/api/auth/login',
        json={'email': 'user@example.com', 'password': 'pass12345'},
    )
    assert login_resp.status_code == 200
    assert cfg.auth_cookie_name in client.cookies
