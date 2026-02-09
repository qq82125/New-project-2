from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def _cfg(crypto_key: str) -> SimpleNamespace:
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
        data_sources_crypto_key=crypto_key,
    )


def test_data_sources_requires_admin(monkeypatch) -> None:
    users = {1: SimpleNamespace(id=1, email='user@example.com', password_hash='x', role='user')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    client = TestClient(main.app)
    token_user = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_user)
    r = client.get('/api/admin/data-sources')
    assert r.status_code == 403


def test_data_sources_encrypts_config(monkeypatch) -> None:
    # Ensure the stored blob is not plaintext password.
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    created = {}

    def _create(_db, name: str, type_: str, config_encrypted: str):
        created['enc'] = config_encrypted
        # minimal object compatible with _ds_out usage
        return SimpleNamespace(id=1, name=name, type=type_, is_active=False, updated_at=datetime.now(timezone.utc))

    def _list(_db):
        return [
            SimpleNamespace(
                id=1,
                name='ds1',
                type='postgres',
                is_active=False,
                updated_at=datetime.now(timezone.utc),
                config_encrypted=created['enc'],
            )
        ]

    monkeypatch.setattr('app.main.create_data_source', _create)
    monkeypatch.setattr('app.main.list_data_sources', _list)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    payload = {
        'name': 'ds1',
        'type': 'postgres',
        'config': {
            'host': 'localhost',
            'port': 5432,
            'database': 'db',
            'username': 'u',
            'password': 'p@ssw0rd',
            'sslmode': 'disable',
        },
    }
    r1 = client.post('/api/admin/data-sources', json=payload)
    assert r1.status_code == 200
    assert 'p@ssw0rd' not in created['enc']

    r2 = client.get('/api/admin/data-sources')
    assert r2.status_code == 200
    items = r2.json()['data']['items']
    assert items[0]['config_preview']['host'] == 'localhost'
    assert items[0]['config_preview']['username'] == 'u'


def test_data_sources_delete_rules(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    # Active cannot be deleted.
    active = SimpleNamespace(id=1, name='ds1', type='postgres', is_active=True, config_encrypted='x', updated_at=datetime.now(timezone.utc))
    monkeypatch.setattr('app.main.get_data_source', lambda _db, _id: active if _id == 1 else None)
    monkeypatch.setattr('app.main.delete_data_source', lambda *_args, **_kwargs: True)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)
    r0 = client.delete('/api/admin/data-sources/1')
    assert r0.status_code == 409

    # Inactive can be deleted.
    inactive = SimpleNamespace(id=2, name='ds2', type='postgres', is_active=False, config_encrypted='x', updated_at=datetime.now(timezone.utc))
    monkeypatch.setattr('app.main.get_data_source', lambda _db, _id: inactive if _id == 2 else None)
    called = {'n': 0}

    def _del(_db, _id):
        called['n'] += 1
        return True

    monkeypatch.setattr('app.main.delete_data_source', _del)
    r1 = client.delete('/api/admin/data-sources/2')
    assert r1.status_code == 200
    assert r1.json()['data']['deleted'] is True
    assert called['n'] == 1
