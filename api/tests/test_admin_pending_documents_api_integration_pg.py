from __future__ import annotations

import json
import tempfile
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
def test_admin_pending_documents_list_and_resolve(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    run_source = f'test_pending_documents_api:{tag}'
    raw_doc_id = uuid.uuid4()
    pending_id = uuid.uuid4()

    # Create a real storage_uri file so the resolve path can replay JSON payload.
    payload = {"name": "测试产品A", "status": "ACTIVE", "source_url": "https://example.test/doc"}
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        storage_uri = f.name

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

        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, :source, :url, 'json', :storage_uri, :sha, NOW(), :run, 'FAILED')
                """
            ),
            {
                'id': str(raw_doc_id),
                'source': 'TEST_SRC',
                'url': 'https://example.test/doc',
                'storage_uri': storage_uri,
                'sha': uuid.uuid4().hex + uuid.uuid4().hex,
                'run': f'source_run:{int(run_id)}',
            },
        )
        db.execute(
            text(
                """
                INSERT INTO pending_documents (
                    id, raw_document_id, source_run_id, reason_code, status, created_at, updated_at
                )
                VALUES (
                    :id, :raw_document_id, :source_run_id, 'NO_REG_NO', 'pending', NOW(), NOW()
                )
                """
            ),
            {
                'id': str(pending_id),
                'raw_document_id': str(raw_doc_id),
                'source_run_id': int(run_id),
            },
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr('app.main.get_user_by_id', lambda _db, user_id: SimpleNamespace(id=user_id, role='admin'))
    old_settings = main_mod._settings
    try:
        main_mod._settings = _auth_cfg
        client = TestClient(app)
        token_admin = main_mod.create_session_token(user_id=2, secret='test-secret', ttl_seconds=3600)
        client.cookies.set('ivd_session', token_admin)

        # 1) list pending
        r1 = client.get('/api/admin/pending-documents?status=pending&limit=10&offset=0')
        assert r1.status_code == 200
        data1 = r1.json()['data']
        assert int(data1['total']) == 1
        assert int(data1['count']) == 1
        item = data1['items'][0]
        assert item['id'] == str(pending_id)
        assert item['raw_document_id'] == str(raw_doc_id)
        assert item['status'] == 'pending'
        assert item['reason_code'] == 'NO_REG_NO'

        # 1b) stats should reflect pending backlog
        r_stats = client.get('/api/admin/pending-documents/stats')
        assert r_stats.status_code == 200
        stats = r_stats.json()['data']
        assert int(stats['backlog']['pending_total']) >= 1
        assert any(x.get('reason_code') == 'NO_REG_NO' for x in stats.get('by_reason_code', []))

        # 2) resolve => must upsert registrations first (via standard upsert path)
        r2 = client.post(
            f'/api/admin/pending-documents/{pending_id}/resolve',
            json={'registration_no': '粤械备20140023', 'product_name': '手工补充名'},
        )
        assert r2.status_code == 200
        data2 = r2.json()['data']
        assert data2['status'] == 'resolved'
        assert data2['registration_no'] == '粤械备20140023'

        with Session(engine) as db:
            reg = db.execute(
                text("SELECT registration_no FROM registrations WHERE registration_no = :n"),
                {"n": "粤械备20140023"},
            ).scalar_one()
            assert reg == "粤械备20140023"
            # registration upsert must be auditable via change_log (entity_type='registration')
            cnt = db.execute(
                text("SELECT COUNT(*) FROM change_log WHERE entity_type = 'registration'"),
            ).scalar_one()
            assert int(cnt) >= 1

    finally:
        main_mod._settings = old_settings
        app.dependency_overrides.pop(get_db, None)
