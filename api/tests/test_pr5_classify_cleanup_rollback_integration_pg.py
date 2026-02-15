from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from datetime import time as dtime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.data_cleanup import rollback_non_ivd_cleanup, run_non_ivd_cleanup
from app.services.reclassify_ivd import run_reclassify_ivd
from it_pg_utils import apply_sql_migrations, assert_table_exists, require_it_db_url


@pytest.mark.integration
def test_reclassify_then_cleanup_then_rollback_real_postgres() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)
        assert_table_exists(conn, "products")
        assert_table_exists(conn, "products_archive")
        assert_table_exists(conn, "change_log")
        assert_table_exists(conn, "change_log_archive")

    pid_ivd = uuid.uuid4()
    pid_non = uuid.uuid4()
    today = date.today()
    ts = datetime.combine(today, dtime(hour=12, minute=0), tzinfo=timezone.utc)

    with Session(engine) as db:
        # Seed 2 products with unknown classification.
        # Names are chosen to be deterministically classified by the rule-first classifier.
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, name, status, is_ivd, ivd_version, raw_json, raw, created_at, updated_at)
                VALUES (:id, :udi, :name, 'ACTIVE', NULL, 1, :raw::jsonb, :raw::jsonb, :ts, :ts)
                """
            ),
            {
                "id": str(pid_ivd),
                "udi": "DI_IT_P5_1",
                "name": "体外诊断试剂盒",
                "raw": '{"source":"it_seed"}',
                "ts": ts,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, name, status, is_ivd, ivd_version, raw_json, raw, created_at, updated_at)
                VALUES (:id, :udi, :name, 'ACTIVE', NULL, 1, :raw::jsonb, :raw::jsonb, :ts, :ts)
                """
            ),
            {
                "id": str(pid_non),
                "udi": "DI_IT_P5_2",
                "name": "医用敷料",
                "raw": '{"source":"it_seed"}',
                "ts": ts,
            },
        )

        # change_log is required for daily_metrics correctness; also verifies archive/restore consistency.
        db.execute(
            text(
                """
                INSERT INTO change_log (id, product_id, entity_type, entity_id, change_type, changed_fields, changed_at, change_date)
                VALUES (:id, :pid, 'product', :pid, 'new', '{}'::jsonb, :ts, :ts)
                """
            ),
            {"id": 910001, "pid": str(pid_ivd), "ts": ts},
        )
        db.execute(
            text(
                """
                INSERT INTO change_log (id, product_id, entity_type, entity_id, change_type, changed_fields, changed_at, change_date)
                VALUES (:id, :pid, 'product', :pid, 'new', '{}'::jsonb, :ts, :ts)
                """
            ),
            {"id": 910002, "pid": str(pid_non), "ts": ts},
        )
        db.commit()

        # 1) reclassify
        res = run_reclassify_ivd(db, dry_run=False)
        assert int(res.scanned) >= 2

        ivd_true = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS TRUE")).scalar() or 0)
        ivd_false = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS FALSE")).scalar() or 0)
        assert ivd_true == 1
        assert ivd_false == 1

        # 2) cleanup
        batch_id = "it_pr5_batch_1"
        cleanup = run_non_ivd_cleanup(db, dry_run=False, recompute_days=3, notes="it_pr5", archive_batch_id=batch_id)
        assert cleanup.deleted_count == 1
        assert cleanup.archived_count == 1
        assert cleanup.archive_batch_id == batch_id

        left_false = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS FALSE")).scalar() or 0)
        assert left_false == 0
        in_arch = int(
            db.execute(text("SELECT COUNT(1) FROM products_archive WHERE archive_batch_id = :bid"), {"bid": batch_id}).scalar()
            or 0
        )
        assert in_arch == 1

        # 3) rollback
        rb = rollback_non_ivd_cleanup(db, archive_batch_id=batch_id, dry_run=False, recompute_days=3)
        assert rb.restored_count == 1

        restored_false = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS FALSE")).scalar() or 0)
        assert restored_false == 1

        # change_log restored
        restored_chg = int(db.execute(text("SELECT COUNT(1) FROM change_log WHERE id = 910002")).scalar() or 0)
        assert restored_chg == 1

    engine.dispose()

