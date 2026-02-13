from __future__ import annotations

import uuid
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


def test_search_full_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))

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
    monkeypatch.setattr('app.main.search_products', lambda *args, **kwargs: ([product], 1))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/search?mode=full&q=test')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_search_full_allows_pro(monkeypatch) -> None:
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
    monkeypatch.setattr('app.main.search_products', lambda *args, **kwargs: ([product], 1))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/search?mode=full&q=test')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert r.json()['data']['items'][0]['product']['name'] == 'Test Kit'


def test_product_detail_full_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))

    pid = uuid.uuid4()
    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')
    product = SimpleNamespace(
        id=pid,
        udi_di='UDI-1',
        reg_no='REG-1',
        name='Test Kit',
        status='active',
        approved_date=None,
        expiry_date=None,
        class_name='II',
        company=company,
    )
    monkeypatch.setattr('app.main.get_product', lambda *args, **kwargs: product)

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get(f'/api/products/{pid}?mode=full')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_product_timeline_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)

    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))
    monkeypatch.setattr('app.main.get_product_timeline', lambda *args, **kwargs: [])

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    pid = uuid.uuid4()
    r = client.get(f'/api/products/{pid}/timeline')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_products_full_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))
    monkeypatch.setattr('app.main.list_full_products', lambda *args, **kwargs: ([], 0))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/products/full')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_products_full_allows_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    user = SimpleNamespace(id=1, email='pro@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=True))
    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')
    product = SimpleNamespace(
        id=uuid.uuid4(),
        udi_di='UDI-1',
        reg_no='REG-1',
        name='Full Library Product',
        status='active',
        approved_date=None,
        expiry_date=None,
        class_name='22',
        ivd_category='reagent',
        company=company,
    )
    monkeypatch.setattr('app.main.list_full_products', lambda *args, **kwargs: ([product], 1))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/products/full')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert r.json()['data']['items'][0]['product']['name'] == 'Full Library Product'


def test_company_tracking_requires_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    user = SimpleNamespace(id=1, email='u@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=False))
    monkeypatch.setattr('app.main.list_company_tracking', lambda *args, **kwargs: ([], 0))

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)
    r = client.get('/api/company-tracking')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'PRO_REQUIRED'


def test_company_tracking_allows_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    user = SimpleNamespace(id=1, email='pro@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=True))
    monkeypatch.setattr(
        'app.main.list_company_tracking',
        lambda *args, **kwargs: (
            [
                {
                    'company_id': str(uuid.uuid4()),
                    'company_name': 'Acme',
                    'country': 'CN',
                    'total_products': 10,
                    'active_products': 8,
                    'last_product_updated_at': None,
                }
            ],
            1,
        ),
    )

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)
    r = client.get('/api/company-tracking')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert r.json()['data']['items'][0]['company_name'] == 'Acme'


def test_company_tracking_detail_pagination_allows_pro(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    user = SimpleNamespace(id=1, email='pro@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.compute_plan', lambda *_args, **_kwargs: SimpleNamespace(is_pro=True))
    monkeypatch.setattr(
        'app.main.get_company_tracking_detail',
        lambda *args, **kwargs: {
            'company': {'id': str(uuid.uuid4()), 'name': 'Acme', 'country': 'CN'},
            'stats': {
                'days': kwargs.get('days', 30),
                'total_products': 10,
                'active_products': 8,
                'expired_products': 1,
                'cancelled_products': 1,
                'last_product_updated_at': None,
                'changes_total': 25,
                'changes_by_type': {'update': 25},
            },
            'recent_changes': [],
            'recent_changes_total': 25,
            'page': kwargs.get('page', 1),
            'page_size': kwargs.get('page_size', 10),
        },
    )

    client = TestClient(app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)
    r = client.get(f'/api/company-tracking/{uuid.uuid4()}?days=30&page=2&page_size=10')
    assert r.status_code == 200
    assert r.json()['code'] == 0
    assert r.json()['data']['page'] == 2
    assert r.json()['data']['page_size'] == 10
    assert r.json()['data']['recent_changes_total'] == 25
