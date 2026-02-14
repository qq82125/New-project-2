from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, assert_table_exists, require_it_db_url


@pytest.mark.integration
def test_pr1_tables_constraints_real_postgres() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)
        for t in (
            "products",
            "products_archive",
            "raw_documents",
            "product_variants",
            "product_params",
            "products_rejected",
            "change_log_archive",
        ):
            assert_table_exists(conn, t)

    now = datetime.now(timezone.utc)
    doc_id = uuid.uuid4()
    sha = "a" * 64

    with Session(engine) as db:
        # raw_documents unique constraint: (source, run_id, sha256)
        db.execute(
            text(
                """
                INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                VALUES (:id, 'NMPA_UDI', 'https://example.com', 'ZIP', '/tmp/x.zip', :sha, :ts, 'run1', 'PENDING')
                """
            ),
            {"id": str(doc_id), "sha": sha, "ts": now},
        )
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO raw_documents (id, source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status)
                    VALUES (:id, 'NMPA_UDI', 'https://example.com', 'ZIP', '/tmp/y.zip', :sha, :ts, 'run1', 'PENDING')
                    """
                ),
                {"id": str(uuid.uuid4()), "sha": sha, "ts": now},
            )
            db.commit()
        db.rollback()

        # product_variants di unique
        db.execute(
            text(
                """
                INSERT INTO product_variants (id, di, registry_no, product_name, is_ivd, created_at, updated_at)
                VALUES (:id, 'DI_X', 'REG_X', 'x', TRUE, :ts, :ts)
                """
            ),
            {"id": str(uuid.uuid4()), "ts": now},
        )
        db.commit()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO product_variants (id, di, registry_no, product_name, is_ivd, created_at, updated_at)
                    VALUES (:id, 'DI_X', 'REG_X', 'x', TRUE, :ts, :ts)
                    """
                ),
                {"id": str(uuid.uuid4()), "ts": now},
            )
            db.commit()
        db.rollback()

        # product_params FK to raw_documents
        db.execute(
            text(
                """
                INSERT INTO product_params (
                    id, di, registry_no, param_code, value_num, value_text, unit,
                    range_low, range_high, conditions, evidence_text, evidence_page,
                    raw_document_id, confidence, extract_version, created_at
                ) VALUES (
                    :id, 'DI_X', 'REG_X', 'PARAM_A', 1.23, NULL, 'mg/mL',
                    NULL, NULL, '{}'::jsonb, 'evidence', 1,
                    :doc_id, 0.5, 'v1', :ts
                )
                """
            ),
            {"id": str(uuid.uuid4()), "doc_id": str(doc_id), "ts": now},
        )
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO product_params (
                        id, di, registry_no, param_code, evidence_text, raw_document_id, confidence, extract_version, created_at
                    ) VALUES (
                        :id, 'DI_X', 'REG_X', 'PARAM_B', 'evidence', :missing, 0.5, 'v1', :ts
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), "missing": str(uuid.uuid4()), "ts": now},
            )
            db.commit()
        db.rollback()

    engine.dispose()

