from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
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


def test_data_sources_supports_local_registry_source(monkeypatch, tmp_path: Path) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    folder = tmp_path / 'registry'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'sample.xlsx').write_bytes(b'PK\x03\x04')

    created = {}

    def _create(_db, name: str, type_: str, config_encrypted: str):
        created['enc'] = config_encrypted
        return SimpleNamespace(id=9, name=name, type=type_, is_active=False, updated_at=datetime.now(timezone.utc))

    def _list(_db):
        return [
            SimpleNamespace(
                id=9,
                name='local-registry',
                type='local_registry',
                is_active=False,
                updated_at=datetime.now(timezone.utc),
                config_encrypted=created['enc'],
            )
        ]

    def _get(_db, _id):
        if _id != 9:
            return None
        return SimpleNamespace(
            id=9,
            name='local-registry',
            type='local_registry',
            is_active=False,
            updated_at=datetime.now(timezone.utc),
            config_encrypted=created['enc'],
        )

    monkeypatch.setattr('app.main.create_data_source', _create)
    monkeypatch.setattr('app.main.list_data_sources', _list)
    monkeypatch.setattr('app.main.get_data_source', _get)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    payload = {
        'name': 'local-registry',
        'type': 'local_registry',
        'config': {
            'folder': str(folder),
            'ingest_new': True,
            'ingest_chunk_size': 3000,
        },
    }
    r1 = client.post('/api/admin/data-sources', json=payload)
    assert r1.status_code == 200

    r2 = client.get('/api/admin/data-sources')
    assert r2.status_code == 200
    items = r2.json()['data']['items']
    assert items[0]['type'] == 'local_registry'
    assert items[0]['config_preview']['folder'] == str(folder)
    assert items[0]['config_preview']['ingest_new'] is True

    r3 = client.post('/api/admin/data-sources/9/test')
    assert r3.status_code == 200
    assert r3.json()['data']['ok'] is True


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


def test_data_sources_update_keeps_password_when_omitted(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    # Existing config includes password.
    existing_cfg = {
        'host': 'localhost',
        'port': 5432,
        'database': 'db',
        'username': 'u',
        'password': 'secret',
        'sslmode': 'disable',
    }
    enc = main.encrypt_json(existing_cfg)
    ds0 = SimpleNamespace(id=1, name='ds1', type='postgres', is_active=False, updated_at=datetime.now(timezone.utc), config_encrypted=enc)
    monkeypatch.setattr('app.main.get_data_source', lambda _db, _id: ds0 if _id == 1 else None)

    seen = {}

    def _update(_db, _id, *, name=None, type_=None, config_encrypted=None):
        seen['name'] = name
        seen['enc'] = config_encrypted
        # Return an object compatible with output.
        return SimpleNamespace(id=_id, name=name, type='postgres', is_active=False, updated_at=datetime.now(timezone.utc))

    monkeypatch.setattr('app.main.update_data_source', _update)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    payload = {
        'name': 'ds1-renamed',
        'config': {
            'host': '127.0.0.1',
            'port': 5432,
            'database': 'db2',
            'username': 'u2',
            # password omitted on purpose
            'sslmode': 'disable',
        },
    }
    r = client.put('/api/admin/data-sources/1', json=payload)
    assert r.status_code == 200

    decrypted = main.decrypt_json(seen['enc'])
    assert decrypted['password'] == 'secret'
    assert decrypted['host'] == '127.0.0.1'
    assert seen['name'] == 'ds1-renamed'


def test_data_sources_activate_and_test_routes_exist(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))

    ds0 = SimpleNamespace(
        id=1,
        name='ds1',
        type='postgres',
        is_active=False,
        updated_at=datetime.now(timezone.utc),
        config_encrypted=main.encrypt_json({'host': 'localhost', 'port': 5432, 'database': 'db', 'username': 'u', 'password': 'p'}),
    )
    monkeypatch.setattr('app.main.get_data_source', lambda _db, _id: ds0 if _id == 1 else None)
    monkeypatch.setattr('app.main.activate_data_source', lambda _db, _id: ds0 if _id == 1 else None)
    monkeypatch.setattr('app.main._test_postgres_connection', lambda _cfg: (True, 'ok'))

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r1 = client.post('/api/admin/data-sources/1/activate')
    assert r1.status_code == 200
    assert r1.json()['data']['id'] == 1

    r2 = client.post('/api/admin/data-sources/1/test')
    assert r2.status_code == 200
    assert r2.json()['data']['ok'] is True


def test_admin_data_quality_run(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr(
        'app.main.run_data_quality_audit',
        lambda *_args, **_kwargs: {
            'generated_at': '2026-02-11T19:00:00+00:00',
            'sample_limit': 20,
            'counters': {'total_ivd': 100, 'name_punct_only': 0},
            'samples': {'name_punct_only': []},
        },
    )
    saved = {}

    def _upsert(_db, key, value):
        saved['key'] = key
        saved['value'] = value
        return SimpleNamespace(config_key=key, config_value=value)

    monkeypatch.setattr('app.main.upsert_admin_config', _upsert)

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r = client.post('/api/admin/data-quality/run?sample_limit=20')
    assert r.status_code == 200
    assert r.json()['data']['report']['counters']['total_ivd'] == 100
    assert saved['key'] == 'data_quality_last'


def test_admin_data_quality_last(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr(
        'app.main.get_admin_config',
        lambda *_args, **_kwargs: SimpleNamespace(
            config_key='data_quality_last',
            config_value={'generated_at': '2026-02-11T19:00:00+00:00', 'counters': {'total_ivd': 99}},
        ),
    )

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)
    r = client.get('/api/admin/data-quality/last')
    assert r.status_code == 200
    assert r.json()['data']['report']['counters']['total_ivd'] == 99


def test_admin_nmpa_query_routes(monkeypatch) -> None:
    users = {2: SimpleNamespace(id=2, email='admin@example.com', password_hash='x', role='admin')}
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: users.get(user_id))
    monkeypatch.setattr('app.main.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr('app.services.crypto.get_settings', lambda: _cfg('unit-test-key'))
    monkeypatch.setattr(
        'app.main.run_nmpa_query_supplement_now',
        lambda *_args, **_kwargs: {'status': 'success', 'scanned': 10, 'updated': 1, 'blocked_412': 0},
    )
    monkeypatch.setattr(
        'app.main.get_admin_config',
        lambda *_args, **_kwargs: SimpleNamespace(config_key='source_nmpa_query_last_run', config_value={'status': 'success'}),
    )

    client = TestClient(main.app)
    token_admin = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token_admin)

    r1 = client.post('/api/admin/source-nmpa-query/run')
    assert r1.status_code == 200
    assert r1.json()['data']['report']['status'] == 'success'

    r2 = client.get('/api/admin/source-nmpa-query/last')
    assert r2.status_code == 200
    assert r2.json()['data']['report']['status'] == 'success'
