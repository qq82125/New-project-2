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
def test_dashboard_lri_endpoints_limit_and_free_pro_redaction(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    # Pick a methodology id (seeded by migration), fallback to manual insert if empty.
    with Session(engine) as db:
        mid = db.execute(text("SELECT id FROM methodology_master ORDER BY created_at ASC LIMIT 1")).scalar()
        if mid is None:
            mid = uuid.uuid4()
            db.execute(
                text(
                    "INSERT INTO methodology_master (id, code, name_cn, is_active, created_at, updated_at) VALUES (:id,'PCR','PCR',TRUE,NOW(),NOW())"
                ),
                {'id': str(mid)},
            )
        db.commit()

    # Insert 3 IVD products + lri_scores with different lri_norm.
    now = datetime.now(timezone.utc)
    regs = []
    prods = []
    with Session(engine) as db:
        for i, norm in enumerate([0.9, 0.7, 0.4], start=1):
            reg_id = uuid.uuid4()
            prod_id = uuid.uuid4()
            regs.append(reg_id)
            prods.append(prod_id)
            db.execute(
                text(
                    "INSERT INTO registrations (id, registration_no, status, raw_json, created_at, updated_at) VALUES (:id, :no, 'ACTIVE', '{}'::jsonb, NOW(), NOW())"
                ),
                {'id': str(reg_id), 'no': f'粤械备2014002{i}'},
            )
            db.execute(
                text(
                    """
                    INSERT INTO products (id, udi_di, name, registration_id, is_ivd, ivd_category, ivd_version, raw_json, created_at, updated_at)
                    VALUES (:id, :di, :name, :rid, TRUE, 'reagent', 1, '{}'::jsonb, NOW(), NOW())
                    """
                ),
                {'id': str(prod_id), 'di': f'UDI-DI-LRI-{i}', 'name': f'测试产品{i}', 'rid': str(reg_id)},
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
                      :id, :rid, :pid, :mid,
                      30, 2, 10, 7,
                      45, 8, 10, 14,
                      77, :norm, :risk, 'lri_v1', :ts
                    )
                    """
                ),
                {
                    'id': str(uuid.uuid4()),
                    'rid': str(reg_id),
                    'pid': str(prod_id),
                    'mid': str(mid),
                    'norm': float(norm),
                    'risk': 'CRITICAL' if norm >= 0.8 else ('HIGH' if norm >= 0.6 else 'MID'),
                    'ts': now,
                },
            )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='user'))
    old_settings = main_mod._settings
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token = main_mod.create_session_token(user_id=1, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token)

        # Free user (redacted): limit must work, and pro-only fields are null.
        monkeypatch.setattr('app.main.compute_plan', lambda _u, _db: SimpleNamespace(is_pro=False))
        r_top = client.get('/api/dashboard/lri/top?limit=2&offset=0')
        assert r_top.status_code == 200
        items = r_top.json()['data']['items']
        assert len(items) == 2
        assert items[0]['product_name'] == '测试产品1'
        assert items[0]['tte_score'] is None
        assert items[0]['competitive_count'] is None

        r_map = client.get('/api/dashboard/lri/map?limit=10&offset=0')
        assert r_map.status_code == 200
        mitems = r_map.json()['data']['items']
        assert len(mitems) >= 1
        assert mitems[0]['gp_new_12m'] is None

        # Pro user: fields present.
        monkeypatch.setattr('app.main.compute_plan', lambda _u, _db: SimpleNamespace(is_pro=True))
        r_top2 = client.get('/api/dashboard/lri/top?limit=1&offset=0')
        assert r_top2.status_code == 200
        it0 = r_top2.json()['data']['items'][0]
        assert it0['product_name'] == '测试产品1'
        assert int(it0['tte_score']) == 45
        assert int(it0['competitive_count']) == 10

        r_map2 = client.get('/api/dashboard/lri/map?limit=10&offset=0')
        assert r_map2.status_code == 200
        assert int(r_map2.json()['data']['items'][0]['gp_new_12m']) == 7
    finally:
        main_mod._settings = old_settings
        app.dependency_overrides.clear()

