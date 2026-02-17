from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    ChangeLog,
    ConflictQueue,
    PendingRecord,
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


@dataclass
class VerifyResult:
    source_key: str
    source_run_id: int
    missing_registration_no_count: int
    registration_upserted_count: int
    pending_records_count: int
    raw_documents_count: int
    valid_registration_no: str
    valid_variant_exists: bool
    missing_variant_exists: bool


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def run_verify(*, cleanup: bool = True) -> VerifyResult:
    source_key = f"TEST_ANCHOR_{_now_tag()}_{uuid4().hex[:6]}".upper()
    valid_reg_raw = f"国械注准TEST{uuid4().hex[:8]}"
    valid_reg_no = normalize_registration_no(valid_reg_raw)
    if not valid_reg_no:
        raise RuntimeError("failed to generate valid registration_no")

    missing_di = f"DI-MISS-{uuid4().hex[:8]}".upper()
    valid_di = f"DI-OK-{uuid4().hex[:8]}".upper()

    with SessionLocal() as db:
        # 1) Register a temporary source definition + config.
        db.add(
            SourceDefinition(
                source_key=source_key,
                display_name=f"Anchor Verify {source_key}",
                entity_scope="UDI",
                default_evidence_grade="A",
                parser_key="udi_di_parser",
                enabled_by_default=False,
            )
        )
        db.flush()

        # runner fetches via external postgres connection; point it back to current DB service.
        source_query = (
            "SELECT * FROM (VALUES "
            f"(NULL::text, '{missing_di}'::text, 'PENDING'::text, '缺锚点样本'::text),"
            f"('{valid_reg_no}'::text, '{valid_di}'::text, 'ACTIVE'::text, '有锚点样本'::text)"
            ") AS t(registration_no, di, status, product_name)"
        )

        db.add(
            SourceConfig(
                source_key=source_key,
                enabled=False,
                fetch_params={
                    "type": "postgres",
                    "connection": {
                        "host": "db",
                        "port": 5432,
                        "database": "nmpa",
                        "username": "nmpa",
                        "password": "nmpa",
                        "source_query": source_query,
                        "batch_size": 100,
                        "cutoff_window_hours": 24,
                    },
                },
                parse_params={},
                upsert_policy={"priority": 20, "conflict": "evidence_then_priority", "allow_overwrite": True},
            )
        )
        db.commit()

        reg_id = None
        run_id = None
        try:
            # 2) Execute runner.
            stats = run_source_by_key(db, source_key=source_key, execute=True)
            run_id = int(stats.source_run_id or 0)
            if run_id <= 0:
                raise AssertionError("source_run_id missing")

            # 3) Assertions required by anchor enforcement.
            if int(stats.missing_registration_no_count) != 1:
                raise AssertionError(
                    f"expected missing_registration_no_count=1, got {stats.missing_registration_no_count}"
                )
            if int(stats.registration_upserted_count) < 1:
                raise AssertionError(
                    f"expected registration_upserted_count>=1, got {stats.registration_upserted_count}"
                )

            pending_count = int(
                db.execute(
                    text(
                        """
                        SELECT COUNT(1)
                        FROM pending_records
                        WHERE source_run_id = :rid
                          AND source_key = :sk
                          AND reason_code = 'MISSING_REGISTRATION_NO'
                        """
                    ),
                    {"rid": run_id, "sk": source_key},
                ).scalar()
                or 0
            )
            if pending_count < 1:
                raise AssertionError("expected pending_records for missing registration_no")

            raw_count = int(
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
            if raw_count < 2:
                raise AssertionError(f"expected raw_documents>=2, got {raw_count}")

            reg = db.scalar(select(Registration).where(Registration.registration_no == valid_reg_no))
            if reg is None:
                raise AssertionError("expected registration upsert for valid registration_no")
            reg_id = reg.id

            valid_variant = db.scalar(select(ProductVariant).where(ProductVariant.di == valid_di))
            missing_variant = db.scalar(select(ProductVariant).where(ProductVariant.di == missing_di))
            if valid_variant is None:
                raise AssertionError("expected variant upsert for valid anchored record")
            if missing_variant is not None:
                raise AssertionError("missing registration_no record must not write product_variants")

            return VerifyResult(
                source_key=source_key,
                source_run_id=run_id,
                missing_registration_no_count=int(stats.missing_registration_no_count),
                registration_upserted_count=int(stats.registration_upserted_count),
                pending_records_count=pending_count,
                raw_documents_count=raw_count,
                valid_registration_no=valid_reg_no,
                valid_variant_exists=True,
                missing_variant_exists=False,
            )
        finally:
            if cleanup:
                if run_id:
                    db.execute(delete(PendingRecord).where(PendingRecord.source_run_id == run_id))
                    db.execute(delete(RegistrationConflictAudit).where(RegistrationConflictAudit.source_run_id == run_id))
                    db.execute(delete(ConflictQueue).where(ConflictQueue.source_run_id == run_id))
                    db.execute(delete(ChangeLog).where(ChangeLog.source_run_id == run_id))
                    db.execute(
                        delete(RawDocument).where(
                            RawDocument.source == source_key,
                            RawDocument.run_id == f"source_run:{run_id}",
                        )
                    )
                    db.execute(delete(SourceRun).where(SourceRun.id == run_id))
                if reg_id is not None:
                    db.execute(delete(Registration).where(Registration.id == reg_id))
                db.execute(delete(ProductVariant).where(ProductVariant.di.in_([valid_di, missing_di])))
                db.execute(delete(SourceConfig).where(SourceConfig.source_key == source_key))
                db.execute(delete(SourceDefinition).where(SourceDefinition.source_key == source_key))
                db.commit()


def main() -> None:
    result = run_verify(cleanup=True)
    print(
        {
            "ok": True,
            "source_key": result.source_key,
            "source_run_id": result.source_run_id,
            "missing_registration_no_count": result.missing_registration_no_count,
            "registration_upserted_count": result.registration_upserted_count,
            "pending_records_count": result.pending_records_count,
            "raw_documents_count": result.raw_documents_count,
            "valid_registration_no": result.valid_registration_no,
            "valid_variant_exists": result.valid_variant_exists,
            "missing_variant_exists": result.missing_variant_exists,
        }
    )


if __name__ == "__main__":
    main()
