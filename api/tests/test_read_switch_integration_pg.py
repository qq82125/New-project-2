from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.main as main_mod
from app.db.session import get_db
from app.main import app
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_product_detail_anchor_resolves_registration_via_variant_registry_no() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    product_id = uuid.uuid4()
    reg_id = uuid.uuid4()
    raw_doc_id = uuid.uuid4()

    with Session(engine) as db:
        # Minimal evidence/run rows for snapshot/event aggregation.
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES ('nmpa_udi', 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            )
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_UDI', 'https://example.test/pkg.zip', 'ZIP', '/tmp/pkg.zip', :sha, NOW(), :run, 'PARSED')
                """
            ),
            {"id": str(raw_doc_id), "sha": "c" * 64, "run": f"source_run:{int(run_id)}"},
        )

        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, approval_date, expiry_date, status, raw_json)
                VALUES (:id, :no, :appr, :exp, 'ACTIVE', '{}'::jsonb)
                """
            ),
            {
                "id": str(reg_id),
                "no": "国械注准20260001",
                "appr": date(2024, 1, 1),
                "exp": date(2030, 1, 1),
            },
        )

        db.execute(
            text(
                """
                INSERT INTO products (
                    id, udi_di, reg_no, name, status, is_ivd, ivd_category, ivd_version,
                    registration_id, raw_json, raw, created_at, updated_at
                )
                VALUES (
                    :id, 'DI-ANCHOR-001', NULL, '锚点测试产品', 'ACTIVE', TRUE, 'reagent', 1,
                    NULL, '{}'::jsonb, '{}'::jsonb, NOW(), NOW()
                )
                """
            ),
            {"id": str(product_id)},
        )

        # registration_id is missing on products; only variant registry_no can anchor to registrations.
        db.execute(
            text(
                """
                INSERT INTO product_variants (id, di, registry_no, product_id, product_name, is_ivd, created_at, updated_at)
                VALUES (:id, 'DI-VAR-ANCHOR-001', :reg_no, :pid, '锚点测试产品', TRUE, NOW(), NOW())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "reg_no": "国械注准（2026）0001",
                "pid": str(product_id),
            },
        )

        db.execute(
            text(
                """
                INSERT INTO nmpa_snapshots (registration_id, raw_document_id, source_run_id, snapshot_date)
                VALUES (:rid, :doc_id, :run_id, CURRENT_DATE)
                """
            ),
            {"rid": str(reg_id), "doc_id": str(raw_doc_id), "run_id": int(run_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO registration_events (registration_id, event_type, event_date, summary, source_run_id)
                VALUES (:rid, 'CHANGE', CURRENT_DATE, 'integration-test', :run_id)
                """
            ),
            {"rid": str(reg_id), "run_id": int(run_id)},
        )
        db.commit()

    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    old_settings = main_mod._settings
    try:
        main_mod._settings = lambda: SimpleNamespace(
            use_registration_anchor=True,
            auth_cookie_name='ivd_session',
            auth_secret='test-secret',
            auth_session_ttl_hours=1,
            auth_cookie_secure=False,
        )

        client = TestClient(app)
        resp = client.get(f"/api/products/{product_id}")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]

        assert data["registration_id"] == str(reg_id)
        assert data["reg_no"] == "国械注准20260001"
        assert data["anchor_summary"]["enabled"] is True
        assert data["anchor_summary"]["source"] == "reg_no_or_variant"
        assert int(data["anchor_summary"]["snapshot_count"]) >= 1
        assert int(data["anchor_summary"]["event_count"]) >= 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        main_mod._settings = old_settings
        engine.dispose()

