from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session

from app.models import (
    ChangeLog,
    PendingDocument,
    PendingRecord,
    Product,
    ProductVariant,
    RawDocument,
    Registration,
    RegistrationConflictAudit,
    SourceConfig,
    SourceDefinition,
    SourceRun,
)
from app.services.ingest_runner import run_source_by_key
from app.services.normalize_keys import normalize_registration_no
from it_pg_utils import apply_sql_migrations, require_it_db_url


def _new_source_key() -> str:
    return f"TEST_CANON_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}".upper()


def _seed_source(db: Session, source_key: str) -> None:
    db.add(
        SourceDefinition(
            source_key=source_key,
            display_name=f"Test {source_key}",
            entity_scope="UDI",
            default_evidence_grade="A",
            parser_key="udi_di_parser",
            enabled_by_default=False,
        )
    )
    db.flush()
    db.add(
        SourceConfig(
            source_key=source_key,
            enabled=False,
            fetch_params={"type": "postgres", "connection": {"host": "db", "port": 5432, "database": "nmpa", "username": "nmpa", "password": "nmpa"}},
            parse_params={},
            upsert_policy={"priority": 20},
        )
    )
    db.commit()


def _cleanup(db: Session, source_key: str, reg_no: str | None, dis: list[str]) -> None:
    run_ids = [int(x) for x in db.scalars(select(SourceRun.id).where(SourceRun.source == f"source_runner:{source_key}")).all()]
    for rid in run_ids:
        db.execute(delete(PendingRecord).where(PendingRecord.source_run_id == rid))
        db.execute(delete(PendingDocument).where(PendingDocument.source_run_id == rid))
        db.execute(delete(RegistrationConflictAudit).where(RegistrationConflictAudit.source_run_id == rid))
        db.execute(delete(ChangeLog).where(ChangeLog.source_run_id == rid))
        db.execute(delete(RawDocument).where(RawDocument.source == source_key, RawDocument.run_id == f"source_run:{rid}"))
        db.execute(delete(SourceRun).where(SourceRun.id == rid))
    if reg_no:
        db.execute(delete(Registration).where(Registration.registration_no == reg_no))
    if dis:
        db.execute(delete(Product).where(Product.udi_di.in_(dis)))
    if dis:
        db.execute(delete(ProductVariant).where(ProductVariant.di.in_(dis)))
    db.execute(delete(SourceConfig).where(SourceConfig.source_key == source_key))
    db.execute(delete(SourceDefinition).where(SourceDefinition.source_key == source_key))
    db.commit()


@pytest.mark.integration
def test_missing_registration_no_goes_raw_plus_pending_only(monkeypatch) -> None:
    # Default contract for this repo: document-only pending queue to avoid duplicate backlog.
    monkeypatch.delenv("PENDING_QUEUE_MODE", raising=False)
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    source_key = _new_source_key()
    missing_di = f"DI-MISS-{uuid4().hex[:8]}".upper()

    with Session(engine) as db:
        _seed_source(db, source_key)
        try:
            monkeypatch.setattr(
                "app.services.ingest_runner._fetch_rows_from_runtime",
                lambda _cfg: [{"di": missing_di, "status": "ACTIVE", "product_name": "missing reg sample"}],
            )
            stats = run_source_by_key(db, source_key=source_key, execute=True)
            run_id = int(stats.source_run_id or 0)

            assert int(stats.missing_registration_no_count) == 1
            assert int(stats.registration_upserted_count) == 0
            assert int(stats.registrations_upserted_count) == 0

            pending_docs = int(
                db.execute(
                    text(
                        """
                        SELECT COUNT(1)
                        FROM pending_documents
                        WHERE source_run_id = :rid
                          AND status = 'pending'
                        """
                    ),
                    {"rid": run_id},
                ).scalar()
                or 0
            )
            pending_recs = int(
                db.execute(
                    text("SELECT COUNT(1) FROM pending_records WHERE source_run_id = :rid AND source_key = :sk"),
                    {"rid": run_id, "sk": source_key},
                ).scalar()
                or 0
            )
            raws = int(
                db.execute(
                    text(
                        """
                        SELECT COUNT(1)
                        FROM raw_documents
                        WHERE source = :sk
                          AND run_id = :run_id
                        """
                    ),
                    {"sk": source_key, "run_id": f"source_run:{run_id}"},
                ).scalar()
                or 0
            )
            regs = int(db.execute(text("SELECT COUNT(1) FROM registrations WHERE registration_no LIKE 'TEST_CANON_%'")).scalar() or 0)
            missing_variant = db.scalar(select(ProductVariant).where(ProductVariant.di == missing_di))

            assert pending_docs >= 1
            assert pending_recs == 0
            assert raws >= 1
            assert regs == 0
            # Contract: missing registration_no must not write product_variants (or registrations/products).
            assert missing_variant is None
        finally:
            _cleanup(db, source_key, reg_no=None, dis=[missing_di])


@pytest.mark.integration
def test_missing_registration_no_document_only_mode_writes_pending_documents_not_records(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("PENDING_QUEUE_MODE", "document_only")
    get_settings.cache_clear()

    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    source_key = _new_source_key()
    missing_di = f"DI-MISS-{uuid4().hex[:8]}".upper()

    with Session(engine) as db:
        _seed_source(db, source_key)
        try:
            monkeypatch.setattr(
                "app.services.ingest_runner._fetch_rows_from_runtime",
                lambda _cfg: [{"di": missing_di, "status": "ACTIVE", "product_name": "missing reg sample"}],
            )
            stats = run_source_by_key(db, source_key=source_key, execute=True)
            run_id = int(stats.source_run_id or 0)

            rec_cnt = int(
                db.execute(
                    text("SELECT COUNT(1) FROM pending_records WHERE source_run_id = :rid AND source_key = :sk"),
                    {"rid": run_id, "sk": source_key},
                ).scalar()
                or 0
            )
            doc_cnt = int(
                db.execute(
                    text("SELECT COUNT(1) FROM pending_documents WHERE source_run_id = :rid AND status = 'pending'"),
                    {"rid": run_id},
                ).scalar()
                or 0
            )
            assert rec_cnt == 0
            assert doc_cnt >= 1
        finally:
            _cleanup(db, source_key, reg_no=None, dis=[missing_di])

    # Restore defaults for other tests.
    monkeypatch.delenv("PENDING_QUEUE_MODE", raising=False)
    get_settings.cache_clear()


@pytest.mark.integration
def test_with_registration_no_upserts_registration_before_variant(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    source_key = _new_source_key()
    di = f"DI-OK-{uuid4().hex[:8]}".upper()
    reg_no = normalize_registration_no(f"国械注准TEST{uuid4().hex[:8]}")
    assert reg_no

    with Session(engine) as db:
        _seed_source(db, source_key)
        try:
            monkeypatch.setattr(
                "app.services.ingest_runner._fetch_rows_from_runtime",
                lambda _cfg: [{"registration_no": reg_no, "di": di, "status": "ACTIVE", "product_name": "anchored sample"}],
            )
            stats = run_source_by_key(db, source_key=source_key, execute=True)

            assert int(stats.missing_registration_no_count) == 0
            assert int(stats.registration_upserted_count) >= 1

            reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no))
            variant = db.scalar(select(ProductVariant).where(ProductVariant.di == di))
            product = db.scalar(select(Product).where(Product.id == variant.product_id)) if variant is not None else None
            assert reg is not None
            assert variant is not None
            assert (variant.registry_no or "") == reg_no
            assert variant.product_id is not None
            assert product is not None
            assert product.registration_id == reg.id
        finally:
            _cleanup(db, source_key, reg_no=reg_no, dis=[di])
