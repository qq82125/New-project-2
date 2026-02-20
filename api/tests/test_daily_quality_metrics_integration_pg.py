from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_quality_metrics_compute_and_upsert() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    from app.services.quality_metrics import compute_daily_quality_metrics, upsert_daily_quality_metrics

    with Session(engine) as db:
        d = date(2026, 2, 20)

        reg_id = db.execute(
            text(
                """
                INSERT INTO registrations (registration_no, field_meta, raw_json, created_at, updated_at)
                VALUES (:reg_no, CAST(:field_meta AS jsonb), '{}'::jsonb, :created_at, NOW())
                RETURNING id
                """
            ),
            {
                "reg_no": f"国械注准20263170001-{uuid.uuid4().hex[:8]}",
                "field_meta": '{"approval_date":{"source_key":"NMPA"},"status":{"source_key":"NMPA"}}',
                "created_at": d,
            },
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO nmpa_snapshots (registration_id, source_run_id, snapshot_date)
                VALUES (:reg_id, NULL, :d)
                """
            ),
            {"reg_id": reg_id, "d": d},
        )

        db.execute(
            text(
                """
                INSERT INTO shadow_diff_errors (source_run_id, reason_code, error, created_at)
                VALUES (NULL, 'PARSE_ERROR', 'it-case', :created_at)
                """
            ),
            {"created_at": d},
        )

        di = f"IT-DI-{uuid.uuid4().hex[:10]}"
        db.execute(
            text(
                """
                INSERT INTO udi_di_master (di, source, first_seen_at, last_seen_at)
                VALUES (:di, 'IT', NOW(), NOW())
                """
            ),
            {"di": di},
        )
        db.execute(
            text(
                """
                INSERT INTO pending_udi_links (di, reason, status)
                VALUES (:di, 'it', 'PENDING')
                """
            ),
            {"di": di},
        )
        db.commit()

        report = compute_daily_quality_metrics(db, as_of=d)
        upsert_daily_quality_metrics(db, report)
        db.commit()

        rows = db.execute(
            text(
                """
                SELECT key, value
                FROM daily_quality_metrics
                WHERE date = :d
                ORDER BY key ASC
                """
            ),
            {"d": d},
        ).fetchall()
        keys = {str(r[0]) for r in rows}
        assert "regno_parse_ok_rate" in keys
        assert "regno_unknown_rate" in keys
        assert "legacy_share" in keys
        assert "diff_success_rate" in keys
        assert "udi_pending_count" in keys
        assert "field_evidence_coverage_rate" in keys
