from __future__ import annotations

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.udi_index import run_udi_device_index
from app.services.udi_params import write_allowlisted_params
from app.services.normalize_keys import normalize_registration_no
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_udi_params_execute_writes_storage_summary() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = uuid4().hex[:8]
    di = f"0694222170{tag}"
    reg = f"REG_PARAMS_{tag}"
    reg_norm = normalize_registration_no(reg)
    assert reg_norm is not None
    source_run_id = int(tag[:6], 16) % 2000000000  # stable-ish and unlikely to collide in shared IT DB
    raw_id = str(uuid4())

    xml = f"""
    <udid version="1.0">
      <devices>
        <device>
          <zxxsdycpbs>{di}</zxxsdycpbs>
          <zczbhhzbapzbh>{reg}</zczbhhzbapzbh>
          <sfyzcbayz>是</sfyzcbayz>
          <cpmctymc>测试产品</cpmctymc>
          <ggxh>X1</ggxh>
          <storageList>
            <storage>
              <cchcztj>冷冻</cchcztj>
              <zdz>-18</zdz>
              <zgz>55</zgz>
              <jldw>℃</jldw>
            </storage>
          </storageList>
          <mjfs>环氧乙烷</mjfs>
        </device>
      </devices>
    </udid>
    """.strip()

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.xml"
        p.write_text(xml, encoding="utf-8")

        with Session(engine) as db:
            # udi_device_index.source_run_id is FK -> source_runs.id
            db.execute(
                text(
                    """
                    INSERT INTO source_runs (id, source, status, records_total, records_success, records_failed)
                    VALUES (:id, 'UDI_INDEX', 'SUCCESS', 0, 0, 0)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": source_run_id},
            )
            db.execute(
                text(
                    """
                    INSERT INTO admin_configs (config_key, config_value)
                    VALUES ('udi_params_allowlist_version', '{"value": 3}'::jsonb)
                    ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value
                    """
                )
            )
            # Raw evidence row for udi_device_index.raw_document_id and product_params.raw_document_id.
            db.execute(
                text(
                    """
                    INSERT INTO raw_documents (id, source, storage_uri, sha256, run_id, source_url, doc_type)
                    VALUES (:id, 'UDI', 'mem://it', :sha, 'it', NULL, 'XML')
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": raw_id, "sha": f"it_{tag}"},
            )
            # Ensure anchor rows exist.
            db.execute(
                text("INSERT INTO registrations (id, registration_no, status) VALUES (:id, :no, 'ACTIVE')"),
                {"id": str(uuid4()), "no": reg_norm},
            )
            # Minimal product row bound to registration_id (required by params writer).
            rid = db.execute(text("SELECT id FROM registrations WHERE registration_no = :n"), {"n": reg_norm}).scalar_one()
            db.execute(
                text(
                    """
                    INSERT INTO products (id, udi_di, reg_no, name, status, is_ivd, ivd_category, ivd_version, registration_id, raw_json, raw)
                    VALUES (:id, :di, :reg_no, :name, 'ACTIVE', true, 'OTHER', 1, :rid, '{}'::jsonb, '{}'::jsonb)
                    """
                ),
                {"id": str(uuid4()), "di": di, "reg_no": reg_norm, "name": "NMPA_NAME", "rid": str(rid)},
            )
            db.commit()

            rep = run_udi_device_index(db, staging_dir=Path(td), raw_document_id=raw_id, source_run_id=source_run_id, dry_run=False)
            assert rep.total_devices == 1

            out = write_allowlisted_params(db, source_run_id=source_run_id, limit=10, only_allowlisted=True, dry_run=False)
            assert out.params_written >= 1

            rows = db.execute(
                text(
                    """
                    SELECT param_code, value_text, conditions, param_key_version
                    FROM product_params
                    WHERE registry_no = :r
                    ORDER BY created_at DESC
                    """
                ),
                {"r": reg_norm},
            ).mappings().all()
            codes = {r["param_code"] for r in rows}
            assert "STORAGE" in codes
            storage = [r for r in rows if r["param_code"] == "STORAGE"][0]
            assert storage["value_text"] is not None and "℃" in str(storage["value_text"])
            assert isinstance(storage["conditions"], dict)
            assert "storages" in storage["conditions"]
            assert int(storage["param_key_version"]) == 3
