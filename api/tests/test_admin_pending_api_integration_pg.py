from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.main as main_mod
from app.common.errors import IngestErrorCode
from app.db.session import get_db
from app.main import app
from app.services.normalize_keys import normalize_registration_no
from it_pg_utils import apply_sql_migrations, require_it_db_url


def _auth_cfg() -> SimpleNamespace:
    return SimpleNamespace(
        auth_secret='test-secret',
        auth_cookie_name='ivd_session',
        auth_session_ttl_hours=1,
        auth_cookie_secure=False,
    )


@pytest.mark.integration
def test_admin_pending_status_filter_and_pagination(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    source_key = f'TEST_PENDING_{tag}'
    run_source = f'test_pending_api:{tag}'
    raw_doc_ids = [uuid.uuid4() for _ in range(4)]

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
                    VALUES (:id, :source, 'https://example.test/x', 'json', '/tmp/x.json', :sha, NOW(), :run, 'FAILED')
                    """
                ),
                {
                    'id': str(rid),
                    'source': source_key,
                    'sha': uuid.uuid4().hex + uuid.uuid4().hex,
                    'run': f'source_run:{int(run_id)}',
                },
            )

        rows = [
            ('open', 'NO_REG_NO', 'A 产品'),
            ('open', 'PARSE_ERROR', 'B 产品'),
            ('resolved', 'NO_REG_NO', 'C 产品'),
            ('ignored', 'NO_REG_NO', 'D 产品'),
        ]
        for i, (status, reason_code, product_name) in enumerate(rows):
            db.execute(
                text(
                    """
                    INSERT INTO pending_records (
                        id, source_key, source_run_id, raw_document_id, payload_hash,
                        registration_no_raw, reason_code, reason,
                        candidate_registry_no, candidate_company, candidate_product_name,
                        status, created_at, updated_at
                    )
                    VALUES (
                        :id, :source_key, :source_run_id, :raw_document_id, :payload_hash,
                        NULL, :reason_code, '{"message":"test"}',
                        NULL, '测试企业', :candidate_product_name,
                        :status, NOW() + (:idx || ' seconds')::interval, NOW()
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
                    'candidate_product_name': product_name,
                    'status': status,
                    'idx': i,
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

        # 1) status filter
        r1 = client.get(f'/api/admin/pending?status=open&source_key={source_key}')
        assert r1.status_code == 200
        body1 = r1.json()['data']
        assert body1['status'] == 'open'
        assert int(body1['total']) == 2
        assert int(body1['count']) == 2
        assert all(str(x['status']).lower() == 'open' for x in body1['items'])
        first = body1['items'][0]
        assert 'id' in first
        assert 'source_key' in first
        assert 'reason_code' in first
        assert 'status' in first
        assert 'created_at' in first
        assert 'candidate_registry_no' in first
        assert 'candidate_company' in first
        assert 'candidate_product_name' in first
        assert 'raw_document_id' in first

        # 2) pagination + ordering (default created_at desc)
        r2 = client.get(f'/api/admin/pending?status=all&source_key={source_key}&limit=2&offset=1')
        assert r2.status_code == 200
        body2 = r2.json()['data']
        assert int(body2['total']) == 4
        assert int(body2['count']) == 2
        assert int(body2['limit']) == 2
        assert int(body2['offset']) == 1
        assert str(body2['order_by']) == 'created_at desc'
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_pending_resolve_success_writes_registration_variant_and_map(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    source_key = f'TEST_PENDING_RESOLVE_{tag}'
    run_source = f'test_pending_resolve:{tag}'
    pending_id = uuid.uuid4()
    raw_doc_id = uuid.uuid4()
    di = f'DI-{tag}'
    reg_input = ' 国械注准 2024 000123 '
    reg_no = normalize_registration_no(reg_input)
    assert reg_no

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO source_definitions (
                    source_key, display_name, entity_scope, default_evidence_grade, parser_key, enabled_by_default
                ) VALUES (:k, :n, 'UDI', 'A', 'udi_di_parser', true)
                ON CONFLICT (source_key) DO NOTHING
                """
            ),
            {'k': source_key, 'n': source_key},
        )
        db.execute(
            text(
                """
                INSERT INTO source_configs (
                    id, source_key, enabled, fetch_params, parse_params, upsert_policy
                ) VALUES (
                    gen_random_uuid(), :k, true, '{}'::jsonb, '{}'::jsonb, '{"priority":1}'::jsonb
                )
                ON CONFLICT (source_key) DO UPDATE SET upsert_policy = EXCLUDED.upsert_policy, enabled = true
                """
            ),
            {'k': source_key},
        )
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
                VALUES (:id, :source, 'https://example.test/raw', 'json', '/tmp/raw.json', :sha, NOW(), :run, 'FAILED')
                """
            ),
            {
                'id': str(raw_doc_id),
                'source': source_key,
                'sha': uuid.uuid4().hex + uuid.uuid4().hex,
                'run': f'source_run:{int(run_id)}',
            },
        )
        db.execute(
            text(
                """
                INSERT INTO pending_records (
                    id, source_key, source_run_id, raw_document_id, payload_hash,
                    registration_no_raw, reason_code, reason,
                    candidate_registry_no, candidate_company, candidate_product_name,
                    status, created_at, updated_at
                )
                VALUES (
                    :id, :source_key, :source_run_id, :raw_document_id, :payload_hash,
                    NULL, 'NO_REG_NO', :reason,
                    NULL, '测试企业', '测试产品',
                    'open', NOW(), NOW()
                )
                """
            ),
            {
                'id': str(pending_id),
                'source_key': source_key,
                'source_run_id': int(run_id),
                'raw_document_id': str(raw_doc_id),
                'payload_hash': uuid.uuid4().hex + uuid.uuid4().hex,
                'reason': '{"message":"test","raw":{"di":"' + di + '","product_name":"测试产品","company_name":"测试企业"}}',
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

        resp = client.post(f'/api/admin/pending/{pending_id}/resolve', json={'registration_no': reg_input})
        assert resp.status_code == 200
        body = resp.json()['data']
        assert body['registration_no'] == reg_no
        assert body['udi_map_written'] is True
        assert body['variant_upserted'] is True

        with Session(engine) as db:
            reg_count = int(
                db.execute(text("SELECT COUNT(*) FROM registrations WHERE registration_no = :n"), {'n': reg_no}).scalar_one()
            )
            assert reg_count == 1
            rec_status = str(
                db.execute(text("SELECT status FROM pending_records WHERE id = :id"), {'id': str(pending_id)}).scalar_one()
            ).lower()
            assert rec_status == 'resolved'
            variant_row = db.execute(
                text("SELECT registry_no FROM product_variants WHERE di = :di"),
                {'di': di},
            ).mappings().one()
            assert str(variant_row['registry_no']) == reg_no
            map_count = int(
                db.execute(
                    text("SELECT COUNT(*) FROM product_udi_map WHERE di = :di AND registration_no = :n"),
                    {'di': di, 'n': reg_no},
                ).scalar_one()
            )
            assert map_count == 1
            pending_log = db.execute(
                text(
                    """
                    SELECT after_raw
                    FROM change_log
                    WHERE entity_type = 'pending_record'
                      AND entity_id = :id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {'id': str(pending_id)},
            ).mappings().one_or_none()
            assert pending_log is not None
            after_raw = pending_log['after_raw'] if isinstance(pending_log['after_raw'], dict) else {}
            assert str(after_raw.get('raw_document_id') or '') == str(raw_doc_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_pending_resolve_invalid_registration_returns_error_code(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    source_key = f'TEST_PENDING_RESOLVE_ERR_{tag}'
    run_source = f'test_pending_resolve_err:{tag}'
    pending_id = uuid.uuid4()
    raw_doc_id = uuid.uuid4()

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
                VALUES (:id, :source, 'https://example.test/raw', 'json', '/tmp/raw.json', :sha, NOW(), :run, 'FAILED')
                """
            ),
            {
                'id': str(raw_doc_id),
                'source': source_key,
                'sha': uuid.uuid4().hex + uuid.uuid4().hex,
                'run': f'source_run:{int(run_id)}',
            },
        )
        db.execute(
            text(
                """
                INSERT INTO pending_records (
                    id, source_key, source_run_id, raw_document_id, payload_hash,
                    registration_no_raw, reason_code, reason, status
                )
                VALUES (
                    :id, :source_key, :source_run_id, :raw_document_id, :payload_hash,
                    NULL, 'NO_REG_NO', '{"message":"test"}', 'open'
                )
                """
            ),
            {
                'id': str(pending_id),
                'source_key': source_key,
                'source_run_id': int(run_id),
                'raw_document_id': str(raw_doc_id),
                'payload_hash': uuid.uuid4().hex + uuid.uuid4().hex,
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

        r1 = client.post(f'/api/admin/pending/{pending_id}/resolve', json={'registration_no': ''})
        assert r1.status_code == 400
        d1 = r1.json().get('detail') or {}
        assert d1.get('code') == IngestErrorCode.E_CANONICAL_KEY_MISSING.value
        assert d1.get('legacy_code') == IngestErrorCode.E_NO_REG_NO.value

        r2 = client.post(f'/api/admin/pending/{pending_id}/resolve', json={'registration_no': '----'})
        assert r2.status_code == 400
        d2 = r2.json().get('detail') or {}
        assert d2.get('code') == IngestErrorCode.E_PARSE_FAILED.value
        assert d2.get('legacy_code') == IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_udi_pending_links_filter_and_pagination(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    di1 = f'DI-U-PEND-{tag}'
    di2 = f'DI-U-RES-{tag}'
    source_key_test = f'TEST_UDI_LINK_{tag}'
    raw_id1 = uuid.uuid4()
    raw_id2 = uuid.uuid4()

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO raw_source_records (
                    id, source, source_run_id, source_url, payload_hash, evidence_grade, observed_at, payload, parse_status
                ) VALUES
                    (:id1, :src, NULL, 'https://example.test/1', :h1, 'B', NOW(), '{}'::jsonb, 'FAILED'),
                    (:id2, :src, NULL, 'https://example.test/2', :h2, 'A', NOW(), '{}'::jsonb, 'PARSED')
                """
            ),
            {
                'id1': str(raw_id1),
                'id2': str(raw_id2),
                'src': source_key_test,
                'h1': uuid.uuid4().hex + uuid.uuid4().hex,
                'h2': uuid.uuid4().hex + uuid.uuid4().hex,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO udi_di_master (id, di, source, raw_source_record_id, payload_hash)
                VALUES
                    (gen_random_uuid(), :di1, :src, :raw1, :ph1),
                    (gen_random_uuid(), :di2, :src, :raw2, :ph2)
                """
            ),
            {
                'di1': di1,
                'di2': di2,
                'src': source_key_test,
                'raw1': str(raw_id1),
                'raw2': str(raw_id2),
                'ph1': uuid.uuid4().hex + uuid.uuid4().hex,
                'ph2': uuid.uuid4().hex + uuid.uuid4().hex,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO pending_udi_links (
                    id, di, reason, reason_code, status, confidence, raw_source_record_id,
                    candidate_company_name, candidate_product_name, created_at, updated_at
                ) VALUES
                    (
                        gen_random_uuid(), :di1,
                        '{"message":"missing reg","raw":{"registration_no":"国械注准20240001"}}',
                        'NO_REG_NO', 'PENDING', 0.55, :raw1,
                        '企业A', '产品A', NOW(), NOW()
                    ),
                    (
                        gen_random_uuid(), :di2,
                        '{"message":"resolved"}',
                        'PARSE_ERROR', 'RESOLVED', 0.90, :raw2,
                        '企业B', '产品B', NOW() + interval '1 second', NOW() + interval '1 second'
                    )
                """
            ),
            {'di1': di1, 'di2': di2, 'raw1': str(raw_id1), 'raw2': str(raw_id2)},
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

        r1 = client.get(f'/api/admin/udi/pending-links?status=pending&source_key={source_key_test}&reason_code=NO_REG_NO')
        assert r1.status_code == 200
        body1 = r1.json()['data']
        assert int(body1['total']) == 1
        assert int(body1['count']) == 1
        it = body1['items'][0]
        assert it['status'] == 'PENDING'
        assert it['source_key'] == source_key_test
        assert it['reason_code'] == 'NO_REG_NO'
        assert it['di'] == di1
        assert it['candidate_registry_no'] == '国械注准20240001'
        assert it['raw_source_record_id'] == str(raw_id1)

        r2 = client.get(f'/api/admin/udi/pending-links?status=all&source_key={source_key_test}&limit=1&offset=1&order_by=created_at desc')
        assert r2.status_code == 200
        body2 = r2.json()['data']
        assert int(body2['total']) == 2
        assert int(body2['count']) == 1
        assert int(body2['limit']) == 1
        assert int(body2['offset']) == 1

        r3 = client.get(f'/api/admin/udi/pending-links?status=all&source_key={source_key_test}&confidence_lt=0.6')
        assert r3.status_code == 200
        body3 = r3.json()['data']
        assert int(body3['total']) == 1
        assert int(body3['count']) == 1
        assert body3['items'][0]['di'] == di1
        assert float(body3['items'][0]['confidence']) < 0.6
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()


@pytest.mark.integration
def test_admin_udi_pending_link_resolve_is_idempotent(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    pending_id = uuid.uuid4()
    raw_id = uuid.uuid4()
    di = f'DI-U-RESOLVE-{tag}'
    reg_input = ' 国械注准 2025 123456 '
    reg_no = normalize_registration_no(reg_input)
    assert reg_no

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO raw_source_records (
                    id, source, source_run_id, source_url, payload_hash, evidence_grade, observed_at, payload, parse_status
                ) VALUES
                    (:id1, 'UDI_DI', NULL, 'https://example.test/resolve', :h1, 'B', NOW(), '{}'::jsonb, 'FAILED')
                """
            ),
            {'id1': str(raw_id), 'h1': uuid.uuid4().hex + uuid.uuid4().hex},
        )
        db.execute(
            text(
                """
                INSERT INTO udi_di_master (id, di, source, raw_source_record_id, payload_hash)
                VALUES (gen_random_uuid(), :di, 'UDI_DI', :raw_id, :ph)
                """
            ),
            {'di': di, 'raw_id': str(raw_id), 'ph': uuid.uuid4().hex + uuid.uuid4().hex},
        )
        db.execute(
            text(
                """
                INSERT INTO pending_udi_links (
                    id, di, reason, reason_code, status, raw_source_record_id, created_at, updated_at
                ) VALUES
                    (:id, :di, '{"message":"need manual bind"}', 'NO_REG_NO', 'PENDING', :raw_id, NOW(), NOW())
                """
            ),
            {'id': str(pending_id), 'di': di, 'raw_id': str(raw_id)},
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

        r1 = client.post(
            f'/api/admin/udi/pending-links/{pending_id}/resolve',
            json={'registration_no': reg_input, 'note': 'manual review pass', 'reason': 'operator confirmed'},
        )
        assert r1.status_code == 200
        b1 = r1.json()['data']
        assert b1['registration_no'] == reg_no
        assert b1['status'] == 'RESOLVED'
        assert b1['idempotent'] is False

        r2 = client.post(
            f'/api/admin/udi/pending-links/{pending_id}/resolve',
            json={'registration_no': reg_input},
        )
        assert r2.status_code == 200
        b2 = r2.json()['data']
        assert b2['registration_no'] == reg_no
        assert b2['status'] == 'RESOLVED'
        assert b2['idempotent'] is True

        with Session(engine) as db:
            reg_count = int(
                db.execute(text("SELECT COUNT(*) FROM registrations WHERE registration_no = :n"), {'n': reg_no}).scalar_one()
            )
            assert reg_count == 1
            map_count = int(
                db.execute(
                    text("SELECT COUNT(*) FROM product_udi_map WHERE registration_no = :n AND di = :di"),
                    {'n': reg_no, 'di': di},
                ).scalar_one()
            )
            assert map_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()
