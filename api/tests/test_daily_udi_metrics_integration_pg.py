from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.metrics import generate_daily_metrics
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_generate_daily_metrics_updates_daily_udi_metrics() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    target_date = date(2026, 2, 17)
    di_a = f'DI-A-{tag}'
    di_b = f'DI-B-{tag}'
    di_c = f'DI-C-{tag}'
    reg_no = f'国械注准{tag}'
    raw_id_open = uuid4()
    raw_id_resolved = uuid4()

    with Session(engine) as db:
        db.execute(
            text(
                """
                INSERT INTO raw_source_records (
                    id, source, source_url, payload_hash, evidence_grade, observed_at, payload, parse_status
                ) VALUES
                    (:id_open, 'UDI_DI', 'https://example.test/open', :h_open, 'B', NOW(), '{}'::jsonb, 'FAILED'),
                    (:id_resolved, 'UDI_DI', 'https://example.test/resolved', :h_resolved, 'B', NOW(), '{}'::jsonb, 'PARSED')
                """
            ),
            {
                'id_open': str(raw_id_open),
                'id_resolved': str(raw_id_resolved),
                'h_open': uuid4().hex + uuid4().hex,
                'h_resolved': uuid4().hex + uuid4().hex,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO udi_di_master (id, di, source, payload_hash, raw_source_record_id)
                VALUES
                    (gen_random_uuid(), :di_a, 'UDI_DI', :ha, :id_open),
                    (gen_random_uuid(), :di_b, 'UDI_DI', :hb, :id_resolved),
                    (gen_random_uuid(), :di_c, 'UDI_DI', :hc, :id_resolved)
                """
            ),
            {
                'di_a': di_a,
                'di_b': di_b,
                'di_c': di_c,
                'ha': uuid4().hex + uuid4().hex,
                'hb': uuid4().hex + uuid4().hex,
                'hc': uuid4().hex + uuid4().hex,
                'id_open': str(raw_id_open),
                'id_resolved': str(raw_id_resolved),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO registrations (id, registration_no)
                VALUES (gen_random_uuid(), :reg_no)
                ON CONFLICT (registration_no) DO NOTHING
                """
            ),
            {'reg_no': reg_no},
        )
        db.execute(
            text(
                """
                INSERT INTO product_udi_map (id, registration_no, di, source, match_type, confidence, raw_source_record_id)
                VALUES
                    (gen_random_uuid(), :reg_no, :di_a, 'test', 'direct', 0.95, :id_open),
                    (gen_random_uuid(), :reg_no, :di_b, 'test', 'direct', 0.95, :id_resolved)
                ON CONFLICT (registration_no, di) DO NOTHING
                """
            ),
            {'reg_no': reg_no, 'di_a': di_a, 'di_b': di_b, 'id_open': str(raw_id_open), 'id_resolved': str(raw_id_resolved)},
        )
        db.execute(
            text(
                """
                INSERT INTO pending_udi_links (
                    id, di, reason, reason_code, status, raw_source_record_id, created_at, updated_at
                ) VALUES
                    (gen_random_uuid(), :di_c, '{"message":"open"}', 'NO_REG_NO', 'PENDING', :id_open, NOW(), NOW()),
                    (gen_random_uuid(), :di_b, '{"message":"done"}', 'NO_REG_NO', 'RESOLVED', :id_resolved, NOW(), NOW())
                """
            ),
            {'di_c': di_c, 'di_b': di_b, 'id_open': str(raw_id_open), 'id_resolved': str(raw_id_resolved)},
        )
        db.commit()

    with Session(engine) as db:
        generate_daily_metrics(db, target_date)
        row = db.execute(
            text(
                """
                SELECT total_di_count, mapped_di_count, unmapped_di_count, coverage_ratio
                FROM daily_udi_metrics
                WHERE metric_date = :d
                """
            ),
            {'d': target_date},
        ).mappings().one()
        assert int(row['total_di_count']) == 3
        assert int(row['mapped_di_count']) == 2
        assert int(row['unmapped_di_count']) == 1
        assert abs(float(row['coverage_ratio']) - (2.0 / 3.0)) < 0.0001

    engine.dispose()

