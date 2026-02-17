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
def test_admin_pending_stats_aggregations(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    run_source = f'test_pending_stats:{tag}'
    source_a = f'TEST_SRC_A_{tag}'
    source_b = f'TEST_SRC_B_{tag}'
    raw_doc_ids = [uuid.uuid4() for _ in range(6)]

    with Session(engine) as db:
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES (:source, 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            ),
            {'source': run_source},
        ).scalar_one()

        for rid in raw_doc_ids:
            db.execute(
                text(
                    """
                    INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                    VALUES (:id, 'TEST_PENDING_STATS', 'https://example.test/raw', 'json', '/tmp/raw.json', :sha, NOW(), :run, 'FAILED')
                    """
                ),
                {
                    'id': str(rid),
                    'sha': uuid.uuid4().hex + uuid.uuid4().hex,
                    'run': f'source_run:{int(run_id)}',
                },
            )

        rows = [
            # source_a: open x2 (NO_REG_NO x1, PARSE_ERROR x1), resolved x1 (within 24h), ignored x1
            (source_a, 'open', 'NO_REG_NO', "NOW() - interval '1 hour'"),
            (source_a, 'open', 'PARSE_ERROR', "NOW() - interval '2 hour'"),
            (source_a, 'resolved', 'NO_REG_NO', "NOW() - interval '3 hour'"),
            (source_a, 'ignored', 'NO_REG_NO', "NOW() - interval '4 hour'"),
            # source_b: open x1 (NO_REG_NO), resolved x1 (older than 7d)
            (source_b, 'open', 'NO_REG_NO', "NOW() - interval '5 hour'"),
            (source_b, 'resolved', 'PARSE_ERROR', "NOW() - interval '10 day'"),
        ]
        for i, (source_key, status, reason_code, created_expr) in enumerate(rows):
            db.execute(
                text(
                    f"""
                    INSERT INTO pending_records (
                        id, source_key, source_run_id, raw_document_id, payload_hash,
                        registration_no_raw, reason_code, reason,
                        candidate_registry_no, candidate_company, candidate_product_name,
                        status, created_at, updated_at
                    )
                    VALUES (
                        :id, :source_key, :source_run_id, :raw_document_id, :payload_hash,
                        NULL, :reason_code, '{{"message":"stats-test"}}',
                        NULL, '测试企业', :candidate_product_name,
                        :status, {created_expr}, NOW()
                    )
                    """
                ),
                {
                    'id': str(uuid.uuid4()),
                    'source_key': source_key,
                    'source_run_id': int(run_id),
                    'raw_document_id': str(raw_doc_ids[i]),
                    'payload_hash': uuid.uuid4().hex + uuid.uuid4().hex,
                    'reason_code': reason_code,
                    'candidate_product_name': f'P-{i}',
                    'status': status,
                },
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

        resp = client.get('/api/admin/pending/stats')
        assert resp.status_code == 200
        data = resp.json()['data']

        by_source = {x['source_key']: x for x in data['by_source_key']}
        assert by_source[source_a]['open'] == 2
        assert by_source[source_a]['resolved'] == 1
        assert by_source[source_a]['ignored'] == 1
        assert by_source[source_b]['open'] == 1
        assert by_source[source_b]['resolved'] == 1
        assert by_source[source_b]['ignored'] == 0

        by_reason = {x['reason_code']: x['open'] for x in data['by_reason_code']}
        assert by_reason['NO_REG_NO'] == 2
        assert by_reason['PARSE_ERROR'] == 1

        backlog = data['backlog']
        assert int(backlog['open_total']) == 3
        assert int(backlog['resolved_last_24h']) == 1
        assert int(backlog['resolved_last_7d']) == 1
        assert int(backlog['windows']['resolved_24h_hours']) == 24
        assert int(backlog['windows']['resolved_7d_days']) == 7
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()

