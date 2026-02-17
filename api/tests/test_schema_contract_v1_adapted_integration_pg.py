from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from it_pg_utils import apply_sql_migrations, require_it_db_url


def assert_columns(conn, table: str, columns: list[str]) -> None:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:t
            """
        ),
        {"t": table},
    ).fetchall()
    existing = {r[0] for r in rows}
    missing = [c for c in columns if c not in existing]
    assert not missing, f"missing columns for {table}: {missing}"


def assert_unique_index_on(conn, table: str, cols: list[str]) -> None:
    # Check if there exists a UNIQUE index whose key columns start with the exact column list.
    # We keep this simple and sufficient for guarding the SSOT contract.
    rows = conn.execute(
        text(
            """
            SELECT
              i.relname AS index_name,
              ix.indisunique AS is_unique,
              array_agg(a.attname ORDER BY x.n) AS cols
            FROM pg_class t
            JOIN pg_index ix ON ix.indrelid = t.oid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, n) ON TRUE
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
            WHERE t.relname = :tname
            GROUP BY i.relname, ix.indisunique
            """
        ),
        {"tname": table},
    ).fetchall()
    want = cols
    for _, is_unique, got_cols in rows:
        if not is_unique:
            continue
        if list(got_cols)[: len(want)] == want:
            return
    raise AssertionError(f"missing unique index on {table}({', '.join(want)})")


@pytest.mark.integration
def test_schema_contract_v1_0_adapted() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

        # Canonical tables/fields used by the v1.0-adapted SSOT.
        assert_columns(
            conn,
            "products",
            [
                "id",
                "udi_di",
                "reg_no",
                "name",
                "class",
                "approved_date",
                "expiry_date",
                "status",
                "is_ivd",
                "ivd_category",
                "ivd_subtypes",
                "ivd_reason",
                "ivd_version",
                "ivd_source",
                "ivd_confidence",
                "company_id",
                "registration_id",
            ],
        )
        assert_columns(
            conn,
            "registrations",
            ["id", "registration_no", "filing_no", "approval_date", "expiry_date", "status"],
        )
        assert_columns(conn, "product_variants", ["id", "di", "registry_no", "product_id"])
        assert_columns(conn, "raw_documents", ["id", "sha256", "storage_uri", "fetched_at", "run_id"])
        assert_columns(conn, "product_params", ["id", "raw_document_id", "evidence_text"])

        # New assetization tables.
        assert_columns(
            conn,
            "nmpa_snapshots",
            [
                "id",
                "registration_id",
                "raw_document_id",
                "source_run_id",
                "snapshot_date",
                "source_url",
                "sha256",
            ],
        )
        assert_columns(
            conn,
            "field_diffs",
            [
                "id",
                "snapshot_id",
                "registration_id",
                "field_name",
                "old_value",
                "new_value",
                "change_type",
                "severity",
                "confidence",
                "source_run_id",
            ],
        )

        # Contract: one snapshot per (registration_id, source_run_id).
        assert_unique_index_on(conn, "nmpa_snapshots", ["registration_id", "source_run_id"])

