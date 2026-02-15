from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


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


def test_admin_products_supports_is_ivd_all(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    admin_user = SimpleNamespace(id=1, email='admin@example.com', password_hash='x', role='admin')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: admin_user if int(user_id) == 1 else None)

    captured = {}

    def _admin_search_products(db, **kwargs):
        captured.update(kwargs)
        return ([], 0)

    monkeypatch.setattr('app.main.admin_search_products', _admin_search_products)

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/admin/products?is_ivd=all')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert captured.get('is_ivd') is None


def test_admin_products_supports_is_ivd_false(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    admin_user = SimpleNamespace(id=1, email='admin@example.com', password_hash='x', role='admin')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: admin_user if int(user_id) == 1 else None)

    captured = {}

    def _admin_search_products(db, **kwargs):
        captured.update(kwargs)
        return ([], 0)

    monkeypatch.setattr('app.main.admin_search_products', _admin_search_products)

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/admin/products?is_ivd=false')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert captured.get('is_ivd') is False

