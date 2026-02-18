from __future__ import annotations

import json
import tempfile
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models import FieldDiff, NmpaSnapshot, RawDocument, Registration, RegistrationEvent, SourceRun
from app.services.time_engine_v1 import derive_registration_events_v1
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_time_engine_v1_detects_renew_from_field_diffs(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_source = f"test_time_engine:{tag}"
    reg_no = f"国械注准TEST{uuid.uuid4().hex[:8]}"
    reg_no2 = f"国械注准TEST{uuid.uuid4().hex[:8]}"
    snap_date1 = date(2026, 2, 10)
    snap_date2 = date(2026, 2, 16)

    # Create a raw json file for RawDocument storage_uri.
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(json.dumps({"registration_no": reg_no}, ensure_ascii=False).encode("utf-8"))
        storage_uri = f.name

    with Session(engine) as db:
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES (:source, 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            ),
            {"source": run_source},
        ).scalar_one()

        raw_id = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_REG', 'https://example.test/raw', 'json', :storage_uri, :sha, NOW(), :run, 'PARSED')
                """
            ),
            {"id": str(raw_id), "storage_uri": storage_uri, "sha": uuid.uuid4().hex + uuid.uuid4().hex, "run": f"source_run:{int(run_id)}"},
        )

        reg = Registration(registration_no=reg_no, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        reg2 = Registration(registration_no=reg_no2, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        db.add_all([reg, reg2])
        db.flush()

        s1 = NmpaSnapshot(
            registration_id=reg.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date1,
            source_url="https://example.test/s1",
            sha256=None,
        )
        s2 = NmpaSnapshot(
            registration_id=reg.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date2,
            source_url="https://example.test/s2",
            sha256=None,
        )
        s1b = NmpaSnapshot(
            registration_id=reg2.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date1,
            source_url="https://example.test/s1b",
            sha256=None,
        )
        s2b = NmpaSnapshot(
            registration_id=reg2.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date2,
            source_url="https://example.test/s2b",
            sha256=None,
        )
        db.add_all([s1, s2, s1b, s2b])
        db.flush()

        # expiry_date increased -> renew (sample 1)
        d = FieldDiff(
            snapshot_id=s2.id,
            registration_id=reg.id,
            field_name="expiry_date",
            old_value="2026-12-31",
            new_value="2027-12-31",
            change_type="MODIFY",
            severity="HIGH",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        # expiry_date increased -> renew (sample 2)
        d2 = FieldDiff(
            snapshot_id=s2b.id,
            registration_id=reg2.id,
            field_name="expiry_date",
            old_value="2025-12-31",
            new_value="2026-12-31",
            change_type="MODIFY",
            severity="HIGH",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        db.add_all([d, d2])
        db.commit()

        res = derive_registration_events_v1(db, since=date(2026, 2, 1), dry_run=False)
        assert res.ok
        assert res.inserted >= 2

        renew = db.scalar(
            select(RegistrationEvent).where(RegistrationEvent.registration_id == reg.id, RegistrationEvent.event_type == "renew")
        )
        assert renew is not None
        assert renew.effective_to is not None
        assert renew.effective_to.isoformat() == "2027-12-31"
        assert renew.event_seq is not None

        renew2 = db.scalar(
            select(RegistrationEvent).where(RegistrationEvent.registration_id == reg2.id, RegistrationEvent.event_type == "renew")
        )
        assert renew2 is not None
        assert renew2.effective_to is not None
        assert renew2.effective_to.isoformat() == "2026-12-31"
        assert renew2.event_seq is not None


@pytest.mark.integration
def test_time_engine_v1_detects_cancel_from_field_diffs() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_source = f"test_time_engine_cancel:{tag}"
    reg_no1 = f"国械注准CANCEL{uuid.uuid4().hex[:8]}"
    reg_no2 = f"国械注准CANCEL{uuid.uuid4().hex[:8]}"
    snap_date = date(2026, 2, 16)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(json.dumps({"registration_no": reg_no1}, ensure_ascii=False).encode("utf-8"))
        storage_uri = f.name

    with Session(engine) as db:
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES (:source, 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            ),
            {"source": run_source},
        ).scalar_one()

        raw_id = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_REG', 'https://example.test/raw', 'json', :storage_uri, :sha, NOW(), :run, 'PARSED')
                """
            ),
            {"id": str(raw_id), "storage_uri": storage_uri, "sha": uuid.uuid4().hex + uuid.uuid4().hex, "run": f"source_run:{int(run_id)}"},
        )

        r1 = Registration(registration_no=reg_no1, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        r2 = Registration(registration_no=reg_no2, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        db.add_all([r1, r2])
        db.flush()

        s1 = NmpaSnapshot(
            registration_id=r1.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date,
            source_url="https://example.test/s_cancel1",
            sha256=None,
        )
        s2 = NmpaSnapshot(
            registration_id=r2.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date,
            source_url="https://example.test/s_cancel2",
            sha256=None,
        )
        db.add_all([s1, s2])
        db.flush()

        d1 = FieldDiff(
            snapshot_id=s1.id,
            registration_id=r1.id,
            field_name="status",
            old_value="ACTIVE",
            new_value="已注销",
            change_type="MODIFY",
            severity="HIGH",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        d2 = FieldDiff(
            snapshot_id=s2.id,
            registration_id=r2.id,
            field_name="status",
            old_value="ACTIVE",
            new_value="撤销",
            change_type="MODIFY",
            severity="HIGH",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        db.add_all([d1, d2])
        db.commit()

        res = derive_registration_events_v1(db, since=date(2026, 2, 1), dry_run=False)
        assert res.ok
        assert res.by_type.get("cancel", 0) >= 2

        e1 = db.scalar(select(RegistrationEvent).where(RegistrationEvent.registration_id == r1.id, RegistrationEvent.event_type == "cancel"))
        e2 = db.scalar(select(RegistrationEvent).where(RegistrationEvent.registration_id == r2.id, RegistrationEvent.event_type == "cancel"))
        assert e1 is not None
        assert e2 is not None


@pytest.mark.integration
def test_time_engine_v1_detects_change_from_field_diffs() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_source = f"test_time_engine_change:{tag}"
    reg_no1 = f"国械注准CHG{uuid.uuid4().hex[:8]}"
    reg_no2 = f"国械注准CHG{uuid.uuid4().hex[:8]}"
    snap_date = date(2026, 2, 16)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
        f.write(json.dumps({"registration_no": reg_no1}, ensure_ascii=False).encode("utf-8"))
        storage_uri = f.name

    with Session(engine) as db:
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES (:source, 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            ),
            {"source": run_source},
        ).scalar_one()

        raw_id = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_REG', 'https://example.test/raw', 'json', :storage_uri, :sha, NOW(), :run, 'PARSED')
                """
            ),
            {"id": str(raw_id), "storage_uri": storage_uri, "sha": uuid.uuid4().hex + uuid.uuid4().hex, "run": f"source_run:{int(run_id)}"},
        )

        r1 = Registration(registration_no=reg_no1, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        r2 = Registration(registration_no=reg_no2, approval_date=None, expiry_date=None, status="ACTIVE", raw_json={})
        db.add_all([r1, r2])
        db.flush()

        s1 = NmpaSnapshot(
            registration_id=r1.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date,
            source_url="https://example.test/s_change1",
            sha256=None,
        )
        s2 = NmpaSnapshot(
            registration_id=r2.id,
            raw_document_id=raw_id,
            source_run_id=int(run_id),
            snapshot_date=snap_date,
            source_url="https://example.test/s_change2",
            sha256=None,
        )
        db.add_all([s1, s2])
        db.flush()

        d1 = FieldDiff(
            snapshot_id=s1.id,
            registration_id=r1.id,
            field_name="product_name",
            old_value="旧名A",
            new_value="新名A",
            change_type="MODIFY",
            severity="MED",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        d2 = FieldDiff(
            snapshot_id=s2.id,
            registration_id=r2.id,
            field_name="model",
            old_value="X1",
            new_value="X2",
            change_type="MODIFY",
            severity="LOW",
            confidence=0.9,
            source_run_id=int(run_id),
        )
        db.add_all([d1, d2])
        db.commit()

        res = derive_registration_events_v1(db, since=date(2026, 2, 1), dry_run=False)
        assert res.ok
        assert res.by_type.get("change", 0) >= 2

        e1 = db.scalar(select(RegistrationEvent).where(RegistrationEvent.registration_id == r1.id, RegistrationEvent.event_type == "change"))
        e2 = db.scalar(select(RegistrationEvent).where(RegistrationEvent.registration_id == r2.id, RegistrationEvent.event_type == "change"))
        assert e1 is not None
        assert e2 is not None
