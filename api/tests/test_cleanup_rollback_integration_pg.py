from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from datetime import time as dtime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.data_cleanup import rollback_non_ivd_cleanup, run_non_ivd_cleanup
from app.services.metrics import generate_daily_metrics
from it_pg_utils import apply_sql_migrations, assert_table_exists, require_it_db_url


@pytest.mark.integration
def test_cleanup_and_rollback_consistency_real_postgres() -> None:
    url = require_it_db_url()

    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)
        assert_table_exists(conn, "products")

    pid_ivd = uuid.uuid4()
    pid_non = uuid.uuid4()
    today = date.today()
    ts = datetime.combine(today, dtime(hour=12, minute=0), tzinfo=timezone.utc)

    with Session(engine) as db:
        # seed products
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, name, status, is_ivd, ivd_category, ivd_version, created_at, updated_at)
                VALUES (:id, :udi, :name, 'ACTIVE', TRUE, 'reagent', 3, :ts, :ts)
                """
                ),
                {"id": str(pid_ivd), "udi": "DI_IT_1", "name": "IVD Product", "ts": ts},
            )
        db.execute(
            text(
                """
                INSERT INTO products (id, udi_di, name, status, is_ivd, ivd_version, created_at, updated_at)
                VALUES (:id, :udi, :name, 'ACTIVE', FALSE, 3, :ts, :ts)
                """
                ),
                {"id": str(pid_non), "udi": "DI_IT_2", "name": "Non IVD Product", "ts": ts},
            )

        # seed change logs (both types). change_date drives daily_metrics.
        db.execute(
            text(
                """
                INSERT INTO change_log (id, product_id, entity_type, entity_id, change_type, changed_fields, changed_at, change_date)
                VALUES (:id, :pid, 'product', :pid, 'new', '{}'::jsonb, :ts, :ts)
                """
                ),
                {"id": 900001, "pid": str(pid_ivd), "ts": ts},
            )
        db.execute(
            text(
                """
                INSERT INTO change_log (id, product_id, entity_type, entity_id, change_type, changed_fields, changed_at, change_date)
                VALUES (:id, :pid, 'product', :pid, 'new', '{}'::jsonb, :ts, :ts)
                """
                ),
                {"id": 900002, "pid": str(pid_non), "ts": ts},
            )
        db.commit()

        raw_cnt = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM change_log c
                    JOIN products p ON p.id = c.product_id
                    WHERE c.change_type = 'new'
                      AND p.is_ivd IS TRUE
                      AND c.change_date >= :d
                      AND c.change_date < (:d + INTERVAL '1 day')
                    """
                ),
                {"d": today},
            ).scalar()
            or 0
        )
        assert raw_cnt == 1

        # metrics should only count IVD (1)
        row0 = generate_daily_metrics(db, today)
        assert int(row0.new_products) == 1

        batch_id = "it_batch_1"
        res = run_non_ivd_cleanup(db, dry_run=False, recompute_days=3, notes="it", archive_batch_id=batch_id)
        assert res.deleted_count == 1
        assert res.archived_count == 1

        # products archived and removed
        non_in_products = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS FALSE")).scalar() or 0)
        assert non_in_products == 0
        in_archive = int(
            db.execute(text("SELECT COUNT(1) FROM products_archive WHERE archive_batch_id = :bid"), {"bid": batch_id}).scalar()
            or 0
        )
        assert in_archive == 1

        # change_log archived and removed
        non_chg_left = int(db.execute(text("SELECT COUNT(1) FROM change_log WHERE product_id = :pid"), {"pid": str(pid_non)}).scalar() or 0)
        assert non_chg_left == 0
        chg_arch = int(
            db.execute(text("SELECT COUNT(1) FROM change_log_archive WHERE archive_batch_id = :bid"), {"bid": batch_id}).scalar()
            or 0
        )
        assert chg_arch >= 1

        row1 = generate_daily_metrics(db, today)
        assert int(row1.new_products) == 1

        rb = rollback_non_ivd_cleanup(db, archive_batch_id=batch_id, dry_run=False, recompute_days=3)
        assert rb.restored_count == 1

        # product restored
        restored_non = int(db.execute(text("SELECT COUNT(1) FROM products WHERE is_ivd IS FALSE")).scalar() or 0)
        assert restored_non == 1

        # change_log restored with same id
        restored_chg = int(db.execute(text("SELECT COUNT(1) FROM change_log WHERE id = 900002")).scalar() or 0)
        assert restored_chg == 1

        row2 = generate_daily_metrics(db, today)
        assert int(row2.new_products) == 1

    engine.dispose()
