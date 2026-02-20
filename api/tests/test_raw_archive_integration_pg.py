from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_archive_raw_execute_keeps_traceability() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        apply_sql_migrations(conn)

    from app.services.raw_archive import archive_raw_data

    old_ts = datetime.now(timezone.utc) - timedelta(days=200)

    with Session(engine) as db:
        raw_doc_id = db.execute(
            text(
                """
                INSERT INTO raw_documents (
                    source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status, parse_log, error
                ) VALUES (
                    'IT', 'https://example.com/doc', 'json', '/tmp/doc.json', repeat('a', 64), :ts, 'it-run', 'PARSED',
                    '{"k":"v"}'::jsonb, 'err'
                ) RETURNING id
                """
            ),
            {"ts": old_ts},
        ).scalar_one()

        rsr_id = db.execute(
            text(
                """
                INSERT INTO raw_source_records (
                    source, source_url, payload_hash, observed_at, payload, parse_status, parse_error
                ) VALUES (
                    'IT', 'https://example.com/src', repeat('b', 64), :ts, '{"x":1}'::jsonb, 'PARSED', 'bad row'
                ) RETURNING id
                """
            ),
            {"ts": old_ts},
        ).scalar_one()
        db.commit()

        report = archive_raw_data(db, older_than_days=180, dry_run=False)
        assert report.updated_documents >= 1
        assert report.updated_source_records >= 1

        doc = db.execute(
            text(
                """
                SELECT id, sha256, archive_status, archived_at, parse_log, error
                FROM raw_documents
                WHERE id = :id
                """
            ),
            {"id": raw_doc_id},
        ).mappings().first()
        assert doc is not None
        assert str(doc["archive_status"]).lower() == "archived"
        assert doc["archived_at"] is not None
        assert doc["sha256"] is not None
        assert doc["error"] is None

        src = db.execute(
            text(
                """
                SELECT id, payload_hash, archive_status, archived_at, payload, parse_error
                FROM raw_source_records
                WHERE id = :id
                """
            ),
            {"id": rsr_id},
        ).mappings().first()
        assert src is not None
        assert str(src["archive_status"]).lower() == "archived"
        assert src["archived_at"] is not None
        assert src["payload_hash"] is not None
        assert src["payload"] is None
        assert src["parse_error"] is None
