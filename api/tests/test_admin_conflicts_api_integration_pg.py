from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

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
def test_admin_conflicts_group_by_registration_no(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_no = f'国械注准TEST{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
    reg_id = uuid4()
    run_id = int(datetime.now(timezone.utc).timestamp())

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, created_at, updated_at)
                VALUES (:id, :registration_no, NOW(), NOW())
                ON CONFLICT (registration_no) DO NOTHING
                """
            ),
            {'id': str(reg_id), 'registration_no': reg_no},
        )
        db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES (:source, 'success', 0, 0, 0, NOW())
                ON CONFLICT DO NOTHING
                """
            ),
            {'source': f'conflicts_test:{run_id}'},
        )
        source_run_id = db.execute(text("SELECT id FROM source_runs WHERE source = :s ORDER BY id DESC LIMIT 1"), {'s': f'conflicts_test:{run_id}'}).scalar_one()
        db.execute(
            text(
                """
                INSERT INTO conflicts_queue (
                    id, registration_no, registration_id, field_name, candidates, status, source_run_id, created_at, updated_at
                ) VALUES
                (
                    gen_random_uuid(), :registration_no, :registration_id, 'status',
                    '[{"source_key":"NMPA_REG","value":"ACTIVE"},{"source_key":"UDI_DI","value":"CANCELLED"}]'::jsonb,
                    'open', :source_run_id, NOW(), NOW()
                ),
                (
                    gen_random_uuid(), :registration_no, :registration_id, 'filing_no',
                    '[{"source_key":"NMPA_REG","value":"A"},{"source_key":"PROCUREMENT_GD","value":"B"}]'::jsonb,
                    'open', :source_run_id, NOW() + interval '1 second', NOW() + interval '1 second'
                )
                """
            ),
            {'registration_no': reg_no, 'registration_id': str(reg_id), 'source_run_id': int(source_run_id)},
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    old_settings = main_mod._settings
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token_admin = main_mod.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token_admin)

        resp = client.get('/api/admin/conflicts?status=open&group_by=registration_no')
        assert resp.status_code == 200
        body = resp.json()['data']
        assert body['group_by'] == 'registration_no'
        assert int(body['count']) >= 1
        rows = [x for x in body['items'] if x.get('registration_no') == reg_no]
        assert len(rows) == 1
        row = rows[0]
        assert int(row['conflict_count']) == 2
        assert 'status' in row['fields']
        assert 'filing_no' in row['fields']
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_conflicts_report_top_fields_counts(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_no = f'国械注准REP{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
    reg_id = uuid4()

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, created_at, updated_at)
                VALUES (:id, :registration_no, NOW(), NOW())
                ON CONFLICT (registration_no) DO NOTHING
                """
            ),
            {'id': str(reg_id), 'registration_no': reg_no},
        )
        db.execute(
            text(
                """
                INSERT INTO conflicts_queue (
                    id, registration_no, registration_id, field_name, candidates, status, created_at, updated_at
                ) VALUES
                (
                    gen_random_uuid(), :registration_no, :registration_id, 'status',
                    '[{"source_key":"NMPA_REG","value":"ACTIVE"}]'::jsonb,
                    'open', NOW(), NOW()
                ),
                (
                    gen_random_uuid(), :registration_no, :registration_id, 'status',
                    '[{"source_key":"UDI_DI","value":"CANCELLED"}]'::jsonb,
                    'open', NOW(), NOW()
                ),
                (
                    gen_random_uuid(), :registration_no, :registration_id, 'filing_no',
                    '[{"source_key":"NMPA_REG","value":"A"}]'::jsonb,
                    'open', NOW(), NOW()
                )
                """
            ),
            {'registration_no': reg_no, 'registration_id': str(reg_id)},
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    old_settings = main_mod._settings
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token_admin = main_mod.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token_admin)

        resp = client.get('/api/admin/conflicts/report?window=7d')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['window'] == '7d'
        top_fields = {str(x['field_name']): int(x['conflict_count']) for x in data['top_fields']}
        assert int(top_fields.get('status', 0)) == 2
        assert int(top_fields.get('filing_no', 0)) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()
