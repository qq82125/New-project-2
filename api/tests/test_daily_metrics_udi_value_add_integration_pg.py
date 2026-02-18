from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.metrics import generate_daily_metrics
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_daily_metrics_contains_udi_value_add_metrics() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    # Use a far-future date to avoid collisions with other integration tests sharing the same IT DB.
    d = date(2030, 1, 1)
    started_at = datetime(2030, 1, 1, 1, 2, 3, tzinfo=timezone.utc)

    tag = uuid4().hex[:8]
    udi_run_id = int(tag[:6], 16) % 2000000000
    reg_no = f"REGUDIQUALITY{tag}".upper()
    di = f"0694222170{tag}".upper()
    raw_id = str(uuid4())
    reg_id = str(uuid4())
    prod_id = str(uuid4())
    raw_run_id = f"it_quality_{tag}"
    raw_sha = f"it_quality_{tag}"

    with Session(engine) as db:
        # source_runs row for UDI index (used to scope udi_device_index metrics)
        db.execute(
            text(
                """
                INSERT INTO source_runs (id, source, status, started_at, records_total, records_success, records_failed)
                VALUES (:id, 'UDI_INDEX', 'SUCCESS', :started_at, 0, 0, 0)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": udi_run_id, "started_at": started_at},
        )
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, storage_uri, sha256, run_id, source_url, doc_type, fetched_at)
                VALUES (:id, 'UDI', 'mem://it', :sha, :run_id, NULL, 'XML', :fa)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": raw_id, "sha": raw_sha, "run_id": raw_run_id, "fa": started_at},
        )
        db.execute(
            text("INSERT INTO registrations (id, registration_no, status) VALUES (:id, :no, 'ACTIVE') ON CONFLICT (registration_no) DO NOTHING"),
            {"id": reg_id, "no": reg_no},
        )
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, reg_no, name, status, is_ivd, ivd_category, ivd_version, registration_id, raw_json, raw, created_at, updated_at)
                VALUES (:id, :di, :reg_no, :name, 'ACTIVE', true, 'OTHER', 1, :rid, CAST(:raw_json AS jsonb), '{}'::jsonb, :ts, :ts)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": prod_id,
                "di": di,
                "reg_no": reg_no,
                "name": "UDI_STUB_PRODUCT",
                "rid": reg_id,
                "raw_json": '{"_stub":{"source_hint":"UDI","verified_by_nmpa":false}}',
                "ts": started_at,
            },
        )
        # udi_device_index row (1 device; has cert, packing, storage)
        db.execute(
            text(
                """
                INSERT INTO udi_device_index (
                  di_norm, registration_no_norm, has_cert,
                  packing_json, storage_json,
                  raw_document_id, source_run_id, created_at, updated_at
                )
                VALUES (
                  :di, :reg, true,
                  CAST(:packing AS jsonb),
                  CAST(:storage AS jsonb),
                  :raw, :srid, :ts, :ts
                )
                ON CONFLICT (di_norm) DO UPDATE SET
                  registration_no_norm = EXCLUDED.registration_no_norm,
                  has_cert = EXCLUDED.has_cert,
                  packing_json = EXCLUDED.packing_json,
                  storage_json = EXCLUDED.storage_json,
                  raw_document_id = EXCLUDED.raw_document_id,
                  source_run_id = EXCLUDED.source_run_id,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "di": di,
                "reg": reg_no,
                "packing": '[{"package_di":"P","package_level":"箱","contains_qty":10,"child_di":"C"}]',
                "storage": '[{"type":"冷冻","min":-18,"max":55,"unit":"℃","range":"-18~55℃"}]',
                "raw": raw_id,
                "srid": udi_run_id,
                "ts": started_at,
            },
        )
        # product_variants upserted that day (value-add)
        db.execute(
            text(
                """
                INSERT INTO product_variants (id, di, registry_no, registration_id, packaging_json, evidence_raw_document_id, created_at, updated_at)
                VALUES (:id, :di, :reg, :rid, '[{"package_di":"P"}]'::jsonb, :raw, :ts, :ts)
                ON CONFLICT (di) DO UPDATE SET
                  registry_no = EXCLUDED.registry_no,
                  registration_id = EXCLUDED.registration_id,
                  packaging_json = EXCLUDED.packaging_json,
                  evidence_raw_document_id = EXCLUDED.evidence_raw_document_id,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {"id": str(uuid4()), "di": di, "reg": reg_no, "rid": reg_id, "raw": raw_id, "ts": started_at},
        )
        # product_params written that day (udi_params_v1)
        db.execute(
            text(
                """
                INSERT INTO product_params (
                  id, di, registry_no, param_code, value_text, conditions, evidence_text, raw_document_id, confidence, extract_version, created_at
                )
                VALUES (
                  :id, :di, :reg, 'STORAGE', '-18~55℃', '{"storages":[{"range":"-18~55℃"}]}'::jsonb,
                  'UDI storage_json', :raw, 0.80, 'udi_params_v1', :ts
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {"id": str(uuid4()), "di": di, "reg": reg_no, "raw": raw_id, "ts": started_at},
        )
        db.commit()

        row = generate_daily_metrics(db, d)
        assert row.metric_date == d
        assert isinstance(row.udi_metrics, dict)
        m = row.udi_metrics

        assert int(m.get("udi_devices_indexed") or 0) == 1
        assert float(m.get("udi_di_non_empty_rate") or 0) == 1.0
        assert float(m.get("udi_reg_non_empty_rate") or 0) == 1.0
        assert float(m.get("udi_has_cert_yes_rate") or 0) == 1.0
        assert int(m.get("udi_unique_reg") or 0) == 1
        assert int(m.get("udi_stub_created") or 0) >= 1
        assert int(m.get("udi_variants_upserted") or 0) >= 1
        assert float(m.get("udi_packings_present_rate") or 0) == 1.0
        assert float(m.get("udi_storages_present_rate") or 0) == 1.0
        assert int(m.get("udi_params_written") or 0) >= 1
