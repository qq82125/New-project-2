from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.nhsa_ingest import ingest_nhsa_from_file, rollback_nhsa_ingest
from it_pg_utils import apply_sql_migrations, assert_table_exists, require_it_db_url


@pytest.mark.integration
def test_nhsa_ingest_and_rollback_real_postgres(tmp_path: Path) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)
        assert_table_exists(conn, "raw_documents")
        assert_table_exists(conn, "nhsa_codes")

    csv_path = tmp_path / "nhsa.csv"
    csv_path.write_text("医保耗材编码,产品名称,规格型号,生产企业\nA123,Foo,10ml,Acme\n", encoding="utf-8")

    with Session(engine) as db:
        res = ingest_nhsa_from_file(db, snapshot_month="2026-01", file_path=str(csv_path), dry_run=False)
        assert res.failed_count == 0
        assert res.upserted == 1

        # Evidence chain exists.
        raw = db.execute(text("select id, source, run_id, parse_status from raw_documents where id = :id"), {"id": str(res.raw_document_id)}).mappings().first()
        assert raw is not None
        assert raw["source"] == "NHSA"
        assert raw["parse_status"] == "PARSED"

        # Structured row exists.
        row = db.execute(
            text(
                "select code, snapshot_month, name, spec, manufacturer, source_run_id from nhsa_codes where code='A123' and snapshot_month='2026-01'"
            )
        ).mappings().first()
        assert row is not None
        assert row["manufacturer"] == "Acme"
        assert int(row["source_run_id"]) == int(res.source_run_id)

        rb = rollback_nhsa_ingest(db, source_run_id=int(res.source_run_id), dry_run=False)
        assert rb["deleted"] >= 1
        left = db.execute(text("select count(1) as c from nhsa_codes where source_run_id=:rid"), {"rid": int(res.source_run_id)}).mappings().first()
        assert int(left["c"]) == 0
