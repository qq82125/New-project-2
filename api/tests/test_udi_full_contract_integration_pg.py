from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models import Registration, UdiDiMaster
from app.services.source_contract import write_udi_contract_record
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_udi_full_contract_parses_packaging_and_storage_and_enforces_anchor() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = uuid4().hex[:12]
    di = f"06942221705071{tag}"
    reg_no = f"粤潮械备20140023-{tag}"

    row_ok = {
        "zxxsdycpbs": di,
        "zczbhhzbapzbh": reg_no,
        "sfyzcbayz": "是",
        "packingList": [
            {
                "bzcpbs": f"2694{tag}",
                "cpbzjb": "箱",
                "bznhxyjcpbssl": "10",
                "bznhxyjbzcpbs": di,
            }
        ],
        "storageList": [
            {"cchcztj": "冷藏", "zdz": "2", "zgz": "8", "jldw": "℃"},
        ],
    }

    row_missing_reg = {
        "zxxsdycpbs": f"06942221705064{tag}",
        "sfyzcbayz": "否",
        "packingList": [],
        "tscchcztj": "产品应储存在干燥、清洁、通风良好环境中",
    }

    with Session(engine) as db:
        before_regs = int(db.execute(text("SELECT COUNT(1) FROM registrations")).scalar_one())

        r1 = write_udi_contract_record(
            db,
            row=row_ok,
            source="UDI_DI",
            source_run_id=1,
            source_url="https://udi.nmpa.gov.cn/download.html",
            evidence_grade="B",
        )
        r2 = write_udi_contract_record(
            db,
            row=row_missing_reg,
            source="UDI_DI",
            source_run_id=1,
            source_url="https://udi.nmpa.gov.cn/download.html",
            evidence_grade="B",
        )
        db.commit()

        after_regs = int(db.execute(text("SELECT COUNT(1) FROM registrations")).scalar_one())

        assert r1.di == di
        assert r1.registration_no_norm is not None
        assert r2.di == row_missing_reg["zxxsdycpbs"]
        assert r2.registration_no_norm is None

        # Packaging/storage JSON landed on DI master.
        master = db.scalar(select(UdiDiMaster).where(UdiDiMaster.di == di))
        assert master is not None
        assert master.has_cert is True
        assert isinstance(master.packaging_json, dict)
        assert master.packaging_json["packings"][0]["package_di"] == f"2694{tag}"
        assert isinstance(master.storage_json, dict)
        assert master.storage_json["storages"][0]["range"] == "2-8℃"

        # The ok row may create a stub registration (canonical anchor).
        assert db.scalar(select(Registration).where(Registration.registration_no == r1.registration_no_norm)) is not None

        # Anchor gate: missing reg_no must not create any additional registrations.
        assert after_regs - before_regs == 1

        master2 = db.scalar(select(UdiDiMaster).where(UdiDiMaster.di == row_missing_reg["zxxsdycpbs"]))
        assert master2 is not None
        assert master2.has_cert is False
        assert isinstance(master2.storage_json, dict)
        assert master2.storage_json["storages"][0]["type"] == "TEXT"
