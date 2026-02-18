from __future__ import annotations

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.udi_index import run_udi_device_index
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_udi_device_index_upsert_from_xml() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = uuid4().hex[:8]
    di = f"06942221705071{tag}"
    reg = f"粤潮械备20140023 {tag}"
    xml = f"""
    <udid version="1.0">
      <devices>
        <device>
          <zxxsdycpbs>{di}</zxxsdycpbs>
          <zczbhhzbapzbh>{reg}</zczbhhzbapzbh>
          <sfyzcbayz>是</sfyzcbayz>
          <cpmctymc>一次性使用采样器</cpmctymc>
          <ggxh>KPCJ12</ggxh>
          <packingList>
            <packing>
              <bzcpbs>2694{tag}</bzcpbs>
              <cpbzjb>箱</cpbzjb>
              <bznhxyjcpbssl>10</bznhxyjcpbssl>
              <bznhxyjbzcpbs>{di}</bznhxyjbzcpbs>
            </packing>
          </packingList>
          <storageList>
            <storage>
              <cchcztj>冷藏</cchcztj>
              <zdz>2</zdz>
              <zgz>8</zgz>
              <jldw>℃</jldw>
            </storage>
          </storageList>
          <versionNumber>1</versionNumber>
          <versionTime>2026-02-15</versionTime>
          <versionStauts>新增</versionStauts>
          <deviceRecordKey>{di}20260215</deviceRecordKey>
        </device>
      </devices>
    </udid>
    """.strip()

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.xml"
        p.write_text(xml, encoding="utf-8")
        with Session(engine) as db:
            rep = run_udi_device_index(
                db,
                staging_dir=Path(td),
                raw_document_id=None,
                source_run_id=123,
                dry_run=False,
            )
            assert rep.total_devices == 1
            assert rep.di_present == 1
            assert rep.reg_present == 1
            assert rep.packing_present == 1
            assert rep.storage_present == 1

            row = db.execute(
                text(
                    """
                    SELECT di_norm, registration_no_norm, has_cert, product_name,
                           packing_json, storage_json, source_run_id
                    FROM udi_device_index
                    WHERE di_norm = :di
                    """
                ),
                {"di": di},
            ).mappings().one()

            assert row["di_norm"] == di
            assert row["has_cert"] is True
            assert int(row["source_run_id"]) == 123
            assert row["product_name"] == "一次性使用采样器"
            assert row["registration_no_norm"] is not None

            pack = row["packing_json"]
            stor = row["storage_json"]
            assert isinstance(pack, list)
            assert isinstance(stor, list)
            assert pack[0]["contains_qty"] == 10
            assert stor[0]["range"] == "2-8℃"

