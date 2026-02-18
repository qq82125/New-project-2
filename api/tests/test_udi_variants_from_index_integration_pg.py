from __future__ import annotations

import json
from pathlib import Path
import tempfile
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_udi_variants_from_device_index_binds_and_marks_unbound() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    with Session(engine) as db:
        reg_id = uuid4()
        raw_id = uuid4()
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no, status)
                VALUES (:id, :no, 'ACTIVE')
                """
            ),
            {"id": str(reg_id), "no": "TESTREGNO123"},
        )
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, storage_uri, sha256, run_id)
                VALUES (:id, 'test', '/tmp/x', 'x', 'r')
                """
            ),
            {"id": str(raw_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO source_runs (id, source, status, records_total, records_success, records_failed)
                VALUES (999, 'test', 'SUCCESS', 0, 0, 0)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

        tag = uuid4().hex[:8]
        bound_di = f"DI_BOUND_{tag}"
        unbound_di = f"DI_UNBOUND_{tag}"
        db.execute(
            text(
                """
            INSERT INTO udi_device_index (di_norm, registration_no_norm, model_spec, sku_code, manufacturer_cn, packing_json, raw_document_id, source_run_id)
            VALUES (:di, :reg, :ggxh, :sku, :m, CAST(:pack AS jsonb), :raw, 999)
            ON CONFLICT (di_norm) DO UPDATE SET registration_no_norm = EXCLUDED.registration_no_norm
            """
        ),
            {
                "di": bound_di,
                "reg": "TESTREGNO123",
                "ggxh": "GG",
                "sku": "SKU",
                "m": "MFG",
                "pack": json.dumps([{"package_di": "P1", "package_level": "1"}], ensure_ascii=True),
                "raw": str(raw_id),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO udi_device_index (di_norm, registration_no_norm, manufacturer_cn, packing_json, raw_document_id, source_run_id)
                VALUES (:di, :reg, :m, CAST(:pack AS jsonb), :raw, 999)
                ON CONFLICT (di_norm) DO UPDATE SET registration_no_norm = EXCLUDED.registration_no_norm
                """
            ),
            {
                "di": unbound_di,
                "reg": "NOT_EXISTS",
                "m": "MFG2",
                "pack": json.dumps([], ensure_ascii=True),
                "raw": str(raw_id),
            },
        )
        db.commit()

        from app.services.udi_variants import upsert_udi_variants_from_device_index

        rep = upsert_udi_variants_from_device_index(db, source_run_id=999, limit=10, dry_run=False)
        assert rep.bound == 1
        assert rep.unbound == 1
        assert rep.upserted == 1

        v = db.execute(
            text(
                "SELECT di, registry_no, registration_id, model_spec, manufacturer, packaging_json, evidence_raw_document_id "
                "FROM product_variants WHERE di = :di"
            ),
            {"di": bound_di},
        ).mappings().one()
        assert v["registry_no"] == "TESTREGNO123"
        assert str(v["registration_id"]) == str(reg_id)
        assert v["model_spec"] == "GG / SKU"
        assert v["manufacturer"] == "MFG"
        assert isinstance(v["packaging_json"], list)
        assert str(v["evidence_raw_document_id"]) == str(raw_id)

        un = db.execute(text("SELECT status FROM udi_device_index WHERE di_norm = :di"), {"di": unbound_di}).scalar_one()
        assert un == "unbound"
