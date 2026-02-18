from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


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


class _DummyDB:
    def execute(self, *_a, **_k):
        class _R:
            def mappings(self):
                return self

            def first(self):
                return None

        return _R()


def test_admin_lri_quality_latest_requires_admin(monkeypatch) -> None:
    monkeypatch.setattr('app.main.get_settings', _auth_cfg)
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='user'))
    client = TestClient(main.app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)
    r = client.get('/api/admin/lri/quality-latest')
    assert r.status_code == 403


def test_admin_lri_quality_latest_returns_defaults(monkeypatch) -> None:
    def _get_db_override():
        yield _DummyDB()

    monkeypatch.setattr('app.main.get_settings', _auth_cfg)
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    main.app.dependency_overrides[main.get_db] = _get_db_override
    client = TestClient(main.app)
    token = main.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)
    r = client.get('/api/admin/lri/quality-latest')
    assert r.status_code == 200
    data = r.json()['data']
    assert data['pending_count'] == 0
    assert data['lri_computed_count'] == 0
    assert 'risk_level_distribution' in data
    main.app.dependency_overrides.clear()

