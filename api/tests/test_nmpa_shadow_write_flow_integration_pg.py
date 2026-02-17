from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_nmpa_shadow_write_two_snapshots_and_diffs() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    from app.services.mapping import ProductRecord
    from app.services.nmpa_assets import shadow_write_nmpa_snapshot_and_diffs

    now = datetime.now(timezone.utc)
    sha = "b" * 64

    with Session(engine) as db:
        # Evidence anchor (package-level doc reused).
        raw_doc_id = db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_UDI', 'https://example.com/pkg.zip', 'archive', '/tmp/pkg.zip', :sha, :ts, 'source_run:1', 'PARSED')
                RETURNING id
                """
            ),
            {"id": str(uuid.uuid4()), "sha": sha, "ts": now},
        ).scalar_one()

        run1 = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES ('nmpa_udi', 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            )
        ).scalar_one()
        run2 = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES ('nmpa_udi', 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            )
        ).scalar_one()

        rec1 = ProductRecord(
            name="试剂A",
            reg_no="REG-001",
            udi_di="DI-001",
            status="active",
            approved_date=date(2020, 1, 1),
            expiry_date=date(2030, 1, 1),
            company_name=None,
            company_country=None,
            class_name="II",
            raw={"filing_no": "F-001"},
        )
        res1 = shadow_write_nmpa_snapshot_and_diffs(
            db,
            record=rec1,
            product_before=None,
            product_after={"name": "试剂A", "class": "II"},
            source_run_id=int(run1),
            raw_document_id=raw_doc_id,
        )
        assert res1.ok

        rec2 = ProductRecord(
            name="试剂A-新名",
            reg_no="REG-001",
            udi_di="DI-001",
            status="cancelled",
            approved_date=date(2020, 1, 1),
            expiry_date=date(2031, 1, 1),
            company_name=None,
            company_country=None,
            class_name="III",
            raw={"filing_no": "F-001"},
        )
        res2 = shadow_write_nmpa_snapshot_and_diffs(
            db,
            record=rec2,
            product_before={"name": "试剂A", "class": "II"},
            product_after={"name": "试剂A-新名", "class": "III"},
            source_run_id=int(run2),
            raw_document_id=raw_doc_id,
        )
        assert res2.ok

        db.commit()

        snaps = db.execute(text("SELECT count(*) FROM nmpa_snapshots WHERE source_run_id IN (:r1, :r2)"), {"r1": run1, "r2": run2}).scalar_one()
        assert snaps == 2

        # Expect at least one diff with correct old/new for status.
        row = db.execute(
            text(
                """
                SELECT old_value, new_value
                FROM field_diffs
                WHERE field_name='status'
                  AND source_run_id=:r2
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"r2": run2},
        ).fetchone()
        assert row is not None
        assert row[0] == "active"
        assert row[1] == "cancelled"

        # Main products schema remains writable and IVD-only semantics are unaffected by shadow writes.
        db.execute(
            text(
                """
                INSERT INTO products (udi_di, name, status, is_ivd, ivd_category, ivd_version, created_at, updated_at, raw_json, raw)
                VALUES ('DI_MAIN_1', '主表产品', 'ACTIVE', TRUE, 'reagent', 1, NOW(), NOW(), '{}'::jsonb, '{}'::jsonb)
                """
            )
        )
        db.commit()
        cnt = db.execute(text("SELECT count(*) FROM products WHERE is_ivd IS TRUE")).scalar_one()
        assert cnt >= 1
