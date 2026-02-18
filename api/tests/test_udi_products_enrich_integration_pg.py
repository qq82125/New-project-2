from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_udi_products_enrich_fill_empty_and_no_override() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    reg_id = uuid4()
    product_id = uuid4()
    raw_id = uuid4()
    tag = uuid4().hex[:8]
    reg_no = f"REG_ENRICH_{tag}"
    di = f"DI_ENRICH_{tag}"

    with Session(engine) as db:
        db.execute(
            text("INSERT INTO registrations (id, registration_no, status) VALUES (:id, :no, 'ACTIVE')"),
            {"id": str(reg_id), "no": reg_no},
        )
        db.execute(
            text(
                "INSERT INTO raw_documents (id, source, storage_uri, sha256, run_id) "
                "VALUES (:id, 'test', '/tmp/x', :sha, :run)"
            ),
            {"id": str(raw_id), "sha": f"x{tag}", "run": f"r{tag}"},
        )
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, reg_no, name, status, is_ivd, ivd_category, ivd_version, registration_id, raw_json, raw)
                VALUES (:id, :di, :reg_no, :name, 'ACTIVE', true, 'OTHER', 1, :rid, CAST(:rj AS jsonb), CAST(:raw AS jsonb))
                """
            ),
            {
                "id": str(product_id),
                "di": di,
                "reg_no": reg_no,
                "name": "NMPA_NAME",
                "rid": str(reg_id),
                "rj": json.dumps({"description": "NMPA_DESC"}, ensure_ascii=True),
                "raw": json.dumps({}, ensure_ascii=True),
            },
        )
        # UDI device index provides alternative values.
        db.execute(
            text(
                """
                INSERT INTO udi_device_index (di_norm, registration_no_norm, product_name, brand, model_spec, description, category_big, product_type, class_code, raw_document_id, source_run_id)
                VALUES (:di, :reg, :pn, :br, :gg, :desc, :qxlb, :cplb, :flbm, :raw, 555)
                ON CONFLICT (di_norm) DO UPDATE SET registration_no_norm = EXCLUDED.registration_no_norm
                """
            ),
            {
                "di": di,
                "reg": reg_no,
                "pn": "UDI_NAME",
                "br": "UDI_BRAND",
                "gg": "GGXH",
                "desc": "UDI_DESC_LONG",
                "qxlb": "QXLB",
                "cplb": "CPLB",
                "flbm": "FLBM",
                "raw": str(raw_id),
            },
        )
        db.commit()

        from app.services.udi_products_enrich import enrich_products_from_udi_device_index

        rep = enrich_products_from_udi_device_index(db, source_run_id=555, limit=10, dry_run=False, description_max_len=10)
        assert rep.updated == 1
        assert rep.failed == 0

        prod = db.execute(text("SELECT name, model, category, raw_json FROM products WHERE id = :id"), {"id": str(product_id)}).mappings().one()
        # Name should NOT be overridden (existing NMPA).
        assert prod["name"] == "NMPA_NAME"
        # Model/category were empty, should be filled.
        assert prod["model"] == "GGXH"
        assert prod["category"] == "QXLB"
        # Description should not override existing top-level NMPA_DESC, but snapshot should exist.
        rj = prod["raw_json"]
        assert rj["description"] == "NMPA_DESC"
        assert "udi_snapshot" in rj
        assert rj["udi_snapshot"]["description"] == "UDI_DESC_L"  # truncated to 10
        assert "aliases" in rj and "udi_names" in rj["aliases"]
