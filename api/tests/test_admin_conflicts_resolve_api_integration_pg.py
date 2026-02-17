from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.main as main_mod
from app.common.errors import IngestErrorCode
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
def test_admin_conflict_resolve_success_records_reason(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_no = f'国械注准R{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
    reg_id = uuid4()
    conflict_id = uuid4()
    source_run = f'conflict_resolve:{datetime.now(timezone.utc).strftime("%s")}'

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, status, created_at, updated_at)
                VALUES (:id, :registration_no, 'ACTIVE', NOW(), NOW())
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
                """
            ),
            {'source': source_run},
        )
        run_id = db.execute(text("SELECT id FROM source_runs WHERE source=:s ORDER BY id DESC LIMIT 1"), {'s': source_run}).scalar_one()
        db.execute(
            text(
                """
                INSERT INTO conflicts_queue (
                    id, registration_no, registration_id, field_name, candidates, status, source_run_id, created_at, updated_at
                ) VALUES (
                    :id, :registration_no, :registration_id, 'status',
                    '[{"source_key":"NMPA_REG","value":"ACTIVE"},{"source_key":"UDI_DI","value":"CANCELLED"}]'::jsonb,
                    'open', :source_run_id, NOW(), NOW()
                )
                """
            ),
            {
                'id': str(conflict_id),
                'registration_no': reg_no,
                'registration_id': str(reg_id),
                'source_run_id': int(run_id),
            },
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    old_settings = main_mod._settings
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin', email='admin@test'))
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token_admin = main_mod.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token_admin)

        reason = 'manual verified from regulator bulletin'
        resp = client.post(
            f'/api/admin/conflicts/{conflict_id}/resolve',
            json={'winner_value': 'CANCELLED', 'reason': reason},
        )
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['status'] == 'resolved'
        assert data['reason'] == reason

        with Session(engine) as db:
            queue_row = db.execute(
                text("SELECT status FROM conflicts_queue WHERE id = :id"),
                {'id': str(conflict_id)},
            ).scalar_one()
            assert str(queue_row).lower() == 'resolved'
            reg_status = db.execute(
                text("SELECT status FROM registrations WHERE registration_no = :n"),
                {'n': reg_no},
            ).scalar_one()
            assert str(reg_status) == 'CANCELLED'
            audit_reason = db.execute(
                text(
                    """
                    SELECT reason
                    FROM registration_conflict_audit
                    WHERE registration_no = :n AND field_name = 'status'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {'n': reg_no},
            ).scalar_one()
            assert reason in str(audit_reason)
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_conflict_resolve_missing_reason_returns_error_code(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_no = f'国械注准M{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'
    reg_id = uuid4()
    conflict_id = uuid4()

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, status, created_at, updated_at)
                VALUES (:id, :registration_no, 'ACTIVE', NOW(), NOW())
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
                ) VALUES (
                    :id, :registration_no, :registration_id, 'status',
                    '[{"source_key":"NMPA_REG","value":"ACTIVE"},{"source_key":"UDI_DI","value":"CANCELLED"}]'::jsonb,
                    'open', NOW(), NOW()
                )
                """
            ),
            {'id': str(conflict_id), 'registration_no': reg_no, 'registration_id': str(reg_id)},
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

        resp = client.post(
            f'/api/admin/conflicts/{conflict_id}/resolve',
            json={'winner_value': 'CANCELLED'},
        )
        assert resp.status_code == 400
        detail = resp.json().get('detail') or {}
        assert detail.get('code') == IngestErrorCode.E_REASON_REQUIRED.value
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()

