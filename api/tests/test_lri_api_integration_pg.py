from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.main as main_mod
from app.db.session import get_db
from app.main import app
from it_pg_utils import apply_sql_migrations, require_it_db_url


def _auth_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        auth_secret='test-secret',
        auth_cookie_name='ivd_session',
        auth_session_ttl_hours=1,
        auth_cookie_secure=False,
    )


@pytest.mark.integration
def test_lri_endpoints_product_and_admin_list(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_id = uuid.uuid4()
    prod_id = uuid.uuid4()

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, status, raw_json, created_at, updated_at)
                VALUES (:id, :no, 'ACTIVE', '{}'::jsonb, NOW(), NOW())
                """
            ),
            {'id': str(reg_id), 'no': '粤械备20140023'},
        )
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, name, registration_id, is_ivd, ivd_version, raw_json, created_at, updated_at)
                VALUES (:id, :di, :name, :rid, TRUE, 1, '{}'::jsonb, NOW(), NOW())
                """
            ),
            {'id': str(prod_id), 'di': 'UDI-DI-TEST-001', 'name': '测试产品A', 'rid': str(reg_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO lri_scores (
                  id, registration_id, product_id, methodology_id,
                  tte_days, renewal_count, competitive_count, gp_new_12m,
                  tte_score, rh_score, cd_score, gp_score,
                  lri_total, lri_norm, risk_level, model_version, calculated_at
                )
                VALUES (
                  :id, :rid, :pid, NULL,
                  30, 2, 10, 3,
                  40, 20, 10, 5,
                  75, 0.5769, 'HIGH', 'lri_v1', NOW()
                )
                """
            ),
            {'id': str(uuid.uuid4()), 'rid': str(reg_id), 'pid': str(prod_id)},
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    monkeypatch.setattr('app.main.compute_plan', lambda _u, _db: SimpleNamespace(is_pro=True))
    old_settings = main_mod._settings
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token = main_mod.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token)

        # Product LRI (pro required).
        r1 = client.get(f'/api/products/{prod_id}/lri')
        assert r1.status_code == 200
        body1 = r1.json()['data']
        assert body1['product_id'] == str(prod_id)
        assert body1['registration_id'] == str(reg_id)
        assert body1['score']['risk_level'] == 'HIGH'

        # Admin list (admin required) returns latest per registration.
        r2 = client.get('/api/admin/lri?limit=10&offset=0')
        assert r2.status_code == 200
        body2 = r2.json()['data']
        assert int(body2['total']) >= 1
        assert any(x.get('registration_no') == '粤械备20140023' for x in (body2.get('items') or []))
    finally:
        main_mod._settings = old_settings
        app.dependency_overrides.clear()

