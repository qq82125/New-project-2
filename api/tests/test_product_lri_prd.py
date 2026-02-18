from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


class _DummyDB:
    def execute(self, *_a, **_k):
        class _R:
            def mappings(self):
                return self

            def first(self):
                # Minimal row shape: free users should only see risk_level/lri_norm/tte_days.
                return {
                    'registration_id': '00000000-0000-0000-0000-000000000001',
                    'product_id': '00000000-0000-0000-0000-000000000002',
                    'methodology_id': None,
                    'methodology_code': None,
                    'methodology_name_cn': None,
                    'tte_days': 10,
                    'renewal_count': 2,
                    'competitive_count': 10,
                    'gp_new_12m': 3,
                    'tte_score': 45,
                    'rh_score': 8,
                    'cd_score': 10,
                    'gp_score': 14,
                    'lri_total': 77,
                    'lri_norm': 0.5923,
                    'risk_level': 'HIGH',
                    'model_version': 'lri_v1',
                    'calculated_at': '2026-02-17T00:00:00Z',
                }

        return _R()


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


def test_product_lri_requires_login(monkeypatch) -> None:
    monkeypatch.setattr('app.main.get_settings', _auth_cfg)
    client = TestClient(main.app)

    r = client.get('/api/products/00000000-0000-0000-0000-000000000000/lri')
    assert r.status_code == 401


def test_product_lri_allows_free_and_redacts_fields(monkeypatch) -> None:
    def _get_db_override():
        yield _DummyDB()

    user = SimpleNamespace(id=1, email='user@example.com', password_hash='x', role='user')
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: user if int(user_id) == 1 else None)
    monkeypatch.setattr('app.main.get_settings', _auth_cfg)
    monkeypatch.setattr('app.main.compute_plan', lambda _u, _db: SimpleNamespace(is_pro=False))
    monkeypatch.setattr(
        'app.main.get_product',
        lambda _db, _pid: SimpleNamespace(id='00000000-0000-0000-0000-000000000000', registration_id='00000000-0000-0000-0000-000000000001'),
    )

    main.app.dependency_overrides[main.get_db] = _get_db_override
    client = TestClient(main.app)
    token = main.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
    client.cookies.set('ivd_session', token)

    r = client.get('/api/products/00000000-0000-0000-0000-000000000000/lri')
    assert r.status_code == 200
    score = (r.json().get('data') or {}).get('score') or {}
    assert score.get('risk_level') == 'HIGH'
    assert score.get('tte_days') == 10
    # redacted for free
    assert score.get('tte_score') is None
    assert score.get('competitive_count') is None

    main.app.dependency_overrides.clear()
