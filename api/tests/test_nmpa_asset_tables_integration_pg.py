from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, assert_table_exists, require_it_db_url


def assert_column_exists(conn, table: str, column: str) -> None:
    ok = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=:t
              AND column_name=:c
            """
        ),
        {"t": table, "c": column},
    ).scalar()
    assert ok == 1, f"missing column: {table}.{column}"


def _has_column(conn, table: str, column: str) -> bool:
    ok = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=:t
              AND column_name=:c
            """
        ),
        {"t": table, "c": column},
    ).scalar()
    return ok == 1


def assert_index_exists(conn, index_name: str) -> None:
    ok = conn.execute(text("SELECT to_regclass(:n)"), {"n": f"public.{index_name}"}).scalar()
    assert ok is not None, f"missing index: {index_name}"


@pytest.mark.integration
def test_nmpa_asset_tables_exist() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)
        assert_table_exists(conn, "nmpa_snapshots")
        assert_table_exists(conn, "field_diffs")
        assert_table_exists(conn, "shadow_diff_errors")

        # Minimal column contract.
        assert_column_exists(conn, "nmpa_snapshots", "registration_id")
        assert_column_exists(conn, "nmpa_snapshots", "raw_document_id")
        assert_column_exists(conn, "nmpa_snapshots", "source_run_id")
        assert_column_exists(conn, "nmpa_snapshots", "snapshot_date")

        assert_column_exists(conn, "field_diffs", "snapshot_id")
        assert_column_exists(conn, "field_diffs", "registration_id")
        assert_column_exists(conn, "field_diffs", "field_name")
        assert_column_exists(conn, "field_diffs", "old_value")
        assert_column_exists(conn, "field_diffs", "new_value")
        assert_column_exists(conn, "field_diffs", "change_type")
        assert_column_exists(conn, "field_diffs", "severity")
        assert_column_exists(conn, "field_diffs", "confidence")
        assert_column_exists(conn, "field_diffs", "changed_at")
        assert_column_exists(conn, "shadow_diff_errors", "reason_code")
        assert_index_exists(conn, "idx_field_diffs_reg_field_changed_at")
        if _has_column(conn, "registrations", "origin_type") and _has_column(conn, "registrations", "management_class"):
            assert_index_exists(conn, "idx_registrations_origin_mgmt")
        if _has_column(conn, "registrations", "first_year"):
            assert_index_exists(conn, "idx_registrations_first_year")
        if _has_column(conn, "registrations", "approval_level"):
            assert_index_exists(conn, "idx_registrations_approval_level")

    # Constraint smoke: one snapshot per (registration_id, source_run_id).
    with Session(engine) as db:
        reg_id = db.execute(
            text(
                """
                INSERT INTO registrations (registration_no, raw_json, created_at, updated_at)
                VALUES ('REG_TEST_1', '{}'::jsonb, NOW(), NOW())
                RETURNING id
                """
            )
        ).scalar_one()
        run_id = db.execute(
            text(
                """
                INSERT INTO source_runs (source, status, records_total, records_success, records_failed, started_at)
                VALUES ('NMPA', 'success', 0, 0, 0, NOW())
                RETURNING id
                """
            )
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO nmpa_snapshots (registration_id, source_run_id, snapshot_date)
                VALUES (:reg_id, :run_id, CURRENT_DATE)
                """
            ),
            {"reg_id": reg_id, "run_id": run_id},
        )
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO nmpa_snapshots (registration_id, source_run_id, snapshot_date)
                    VALUES (:reg_id, :run_id, CURRENT_DATE)
                    """
                ),
                {"reg_id": reg_id, "run_id": run_id},
            )
            db.commit()
        db.rollback()
