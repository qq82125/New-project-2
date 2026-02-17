from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.normalize_keys import normalize_registration_no
from app.services.source_contract import registration_contract_summary, upsert_registration_with_contract
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_registration_conflict_resolution_by_grade_priority_time() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    raw_reg_no = f"TEST-REG-{uuid4().hex[:12]}"
    reg_no = normalize_registration_no(raw_reg_no)
    assert reg_no
    t0 = datetime.now(timezone.utc)

    with Session(engine) as db:
        # 1) create baseline by grade B / priority 50
        r1 = upsert_registration_with_contract(
                db,
                registration_no=raw_reg_no,
            incoming_fields={"status": "ACTIVE"},
            source="SRC_A",
            source_run_id=None,
            evidence_grade="B",
            source_priority=50,
            observed_at=t0,
            raw_payload={"status": "ACTIVE"},
        )
        db.commit()
        assert r1.created is True

        # 2) lower evidence grade C should lose, even with better priority/newer time
        upsert_registration_with_contract(
                db,
                registration_no=raw_reg_no,
            incoming_fields={"status": "CANCELLED"},
            source="SRC_B",
            source_run_id=None,
            evidence_grade="C",
            source_priority=1,
            observed_at=t0 + timedelta(minutes=1),
            raw_payload={"status": "CANCELLED"},
        )
        db.commit()

        # 3) same grade B but worse priority should lose
        upsert_registration_with_contract(
                db,
                registration_no=raw_reg_no,
            incoming_fields={"status": "EXPIRED"},
            source="SRC_C",
            source_run_id=None,
            evidence_grade="B",
            source_priority=100,
            observed_at=t0 + timedelta(minutes=2),
            raw_payload={"status": "EXPIRED"},
        )
        db.commit()

        # 4) same grade B but better priority should win
        upsert_registration_with_contract(
                db,
                registration_no=raw_reg_no,
            incoming_fields={"status": "CANCELLED"},
            source="SRC_D",
            source_run_id=None,
            evidence_grade="B",
            source_priority=20,
            observed_at=t0 + timedelta(minutes=3),
            raw_payload={"status": "CANCELLED"},
        )
        db.commit()

        row = db.execute(
            text(
                """
                SELECT status, raw_json
                FROM registrations
                WHERE registration_no = :no
                """
            ),
            {"no": reg_no},
        ).mappings().one()
        assert row["status"] == "CANCELLED"
        raw_json = row["raw_json"] if isinstance(row["raw_json"], dict) else {}
        prov = raw_json.get("_contract_provenance") if isinstance(raw_json, dict) else {}
        assert isinstance(prov, dict)
        assert isinstance(prov.get("status"), dict)
        assert prov["status"].get("evidence_grade") == "B"
        assert int(prov["status"].get("source_priority")) == 20

        # only "new" + one winning update expected
        cnt = db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM change_log c
                JOIN registrations r ON r.id = c.entity_id
                WHERE c.entity_type = 'registration'
                  AND r.registration_no = :no
                """
            ),
            {"no": reg_no},
        ).scalar_one()
        assert int(cnt) == 2

        summary = registration_contract_summary(
            db,
            start=t0 - timedelta(minutes=1),
            end=t0 + timedelta(minutes=10),
        )
        assert int(summary["totals"]["rejected_total"]) >= 2


@pytest.mark.integration
def test_registration_conflict_tie_goes_to_conflicts_queue() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    raw_reg_no = f"TEST-TIE-{uuid4().hex[:12]}"
    reg_no = normalize_registration_no(raw_reg_no)
    assert reg_no
    t0 = datetime.now(timezone.utc).replace(microsecond=0)

    with Session(engine) as db:
        upsert_registration_with_contract(
            db,
            registration_no=raw_reg_no,
            incoming_fields={"status": "ACTIVE"},
            source="SRC_A",
            source_run_id=None,
            evidence_grade="B",
            source_priority=50,
            observed_at=t0,
            raw_payload={"status": "ACTIVE"},
        )
        db.commit()

        # Same grade + same priority + same observed_at + different value => queue (manual required).
        upsert_registration_with_contract(
            db,
            registration_no=raw_reg_no,
            incoming_fields={"status": "CANCELLED"},
            source="SRC_B",
            source_run_id=None,
            evidence_grade="B",
            source_priority=50,
            observed_at=t0,
            raw_payload={"status": "CANCELLED"},
        )
        db.commit()

        row = db.execute(
            text("SELECT status FROM registrations WHERE registration_no = :no"),
            {"no": reg_no},
        ).mappings().one()
        assert row["status"] == "ACTIVE"

        q = db.execute(
            text(
                """
                SELECT status, field_name, candidates
                FROM conflicts_queue
                WHERE registration_no = :no
                  AND field_name = 'status'
                  AND status = 'open'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"no": reg_no},
        ).mappings().one()
        assert q["status"] == "open"
        assert q["field_name"] == "status"
        candidates = q["candidates"] if isinstance(q["candidates"], list) else []
        values = {str(x.get("value")) for x in candidates if isinstance(x, dict)}
        assert "ACTIVE" in values
        assert "CANCELLED" in values
