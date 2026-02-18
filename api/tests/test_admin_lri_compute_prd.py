from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


class _DummyDB:
    pass


def _auth_cfg() -> SimpleNamespace:
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


def test_admin_lri_compute_requires_admin(monkeypatch) -> None:
    def _get_db_override():
        yield _DummyDB()

    # Logged in but non-admin should be forbidden.
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='user'))
    monkeypatch.setattr('app.main.get_settings', _auth_cfg)

    main.app.dependency_overrides[main.get_db] = _get_db_override
    client = TestClient(main.app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.post('/api/admin/lri/compute', json={'date': '2026-02-17', 'model_version': 'lri_v1', 'upsert': True})
    assert r.status_code == 403

    main.app.dependency_overrides.clear()


def test_admin_lri_compute_calls_compute_and_returns_envelope(monkeypatch) -> None:
    def _get_db_override():
        yield _DummyDB()

    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    monkeypatch.setattr('app.main.get_settings', _auth_cfg)

    class _Res:
        ok = True
        dry_run = False
        date = '2026-02-17'
        model_version = 'lri_v1'
        upsert_mode = True
        would_write = 10
        wrote = 10
        risk_dist = {'LOW': 1}
        missing_methodology_ratio = 0.1
        error = None

    monkeypatch.setattr('app.services.lri_v1.compute_lri_v1', lambda *_a, **_k: _Res())

    main.app.dependency_overrides[main.get_db] = _get_db_override
    client = TestClient(main.app)
    token = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.post('/api/admin/lri/compute', json={'date': '2026-02-17', 'model_version': 'lri_v1', 'upsert': True})
    assert r.status_code == 200
    body = r.json()
    assert body['code'] == 0
    assert body['data']['wrote'] == 10
    assert body['data']['risk_dist']['LOW'] == 1

    main.app.dependency_overrides.clear()

