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


def test_dashboard_breakdown_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    # Free plan: trend_range_days <= 30 is treated as non-pro in current entitlement model.
    monkeypatch.setattr('app.main.get_entitlements', lambda *_args, **_kwargs: SimpleNamespace(trend_range_days=30))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/dashboard/breakdown')
    assert r.status_code == 403


def test_dashboard_breakdown_returns_envelope(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='pro@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.get_entitlements', lambda *_args, **_kwargs: SimpleNamespace(trend_range_days=365))

    monkeypatch.setattr(
        'app.main.get_breakdown',
        lambda *_args, **_kwargs: {
            'total_ivd_products': 3,
            'by_ivd_category': [('REAGENT', 2), ('INSTRUMENT', 1)],
            'by_source': [('NMPA_UDI', 3)],
        },
    )

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/dashboard/breakdown?limit=10')
    assert r.status_code == 200
    body = r.json()
    assert body['code'] == 0
    assert body['data']['total_ivd_products'] == 3
    assert body['data']['by_ivd_category'][0]['key'] == 'REAGENT'
    assert body['data']['by_source'][0]['key'] == 'NMPA_UDI'

