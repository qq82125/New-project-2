from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.models import ChangeLog, DataCleanupRun, Product
from app.services.metrics import regenerate_daily_metrics


@dataclass
class CleanupResult:
    run_id: int
    dry_run: bool
    target_count: int
    archived_count: int
    deleted_count: int
    recomputed_days: int
    notes: dict[str, Any]


@dataclass
class RollbackResult:
    archive_batch_id: str
    dry_run: bool
    target_count: int
    restored_count: int
    skipped_existing: int


def _count_targets(db: Session) -> int:
    stmt = select(func.count(Product.id)).where(Product.is_ivd.is_(False))
    return int(db.scalar(stmt) or 0)


def run_non_ivd_cleanup(
    db: Session,
    *,
    dry_run: bool,
    recompute_days: int = 365,
    notes: str | None = None,
    archive_batch_id: str | None = None,
) -> CleanupResult:
    target_count = _count_targets(db)
    batch_id = str(archive_batch_id or '').strip() or f"non_ivd_cleanup_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run = DataCleanupRun(
        dry_run=bool(dry_run),
        archived_count=(target_count if dry_run else 0),
        deleted_count=0,
        notes=(f"{notes or ''} archive_batch_id={batch_id}".strip()),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if dry_run:
        return CleanupResult(
            run_id=int(run.id),
            dry_run=True,
            target_count=target_count,
            archived_count=target_count,
            deleted_count=0,
            recomputed_days=0,
            notes={'mode': 'dry_run'},
        )

    archived_count = 0
    deleted_count = 0
    try:
        # 1) archive target rows
        archived_count = int(
            db.execute(
                text(
                    """
                    INSERT INTO products_archive (
                        id, udi_di, reg_no, name, class, approved_date, expiry_date,
                        model, specification, category, status,
                        is_ivd, ivd_category, ivd_subtypes, ivd_reason, ivd_version,
                        company_id, registration_id, raw_json, raw, created_at, updated_at,
                        cleanup_run_id, archive_batch_id, archive_reason
                    )
                    SELECT
                        p.id, p.udi_di, p.reg_no, p.name, p.class, p.approved_date, p.expiry_date,
                        p.model, p.specification, p.category, p.status,
                        p.is_ivd, p.ivd_category, p.ivd_subtypes, p.ivd_reason, p.ivd_version,
                        p.company_id, p.registration_id, p.raw_json, p.raw, p.created_at, p.updated_at,
                        :cleanup_run_id, :archive_batch_id, 'non_ivd_cleanup'
                    FROM products p
                    WHERE p.is_ivd IS FALSE
                    """
                ),
                {'cleanup_run_id': int(run.id), 'archive_batch_id': batch_id},
            ).rowcount
            or 0
        )

        # 2) archive then delete related change logs (evidence chain)
        db.execute(
            text(
                """
                INSERT INTO change_log_archive (
                    id, product_id, entity_type, entity_id, change_type,
                    changed_fields, before_json, after_json, before_raw, after_raw,
                    source_run_id, changed_at, change_date,
                    cleanup_run_id, archive_batch_id, archive_reason
                )
                SELECT
                    c.id, c.product_id, c.entity_type, c.entity_id, c.change_type,
                    c.changed_fields, c.before_json, c.after_json, c.before_raw, c.after_raw,
                    c.source_run_id, c.changed_at, c.change_date,
                    :cleanup_run_id, :archive_batch_id, 'non_ivd_cleanup'
                FROM change_log c
                WHERE c.product_id IN (SELECT p.id FROM products p WHERE p.is_ivd IS FALSE)
                """
            ),
            {'cleanup_run_id': int(run.id), 'archive_batch_id': batch_id},
        )
        db.execute(delete(ChangeLog).where(ChangeLog.product_id.in_(select(Product.id).where(Product.is_ivd.is_(False)))))

        # 3) delete target products
        deleted_count = int(db.execute(delete(Product).where(Product.is_ivd.is_(False))).rowcount or 0)

        if archived_count != deleted_count:
            raise RuntimeError(
                f'archive/delete mismatch: archived_count={archived_count} deleted_count={deleted_count}'
            )

        run.archived_count = archived_count
        run.deleted_count = deleted_count
        run.notes = (f"{notes or ''} archive_batch_id={batch_id}".strip())
        db.add(run)
        db.commit()

        # 4) recompute daily metrics based on IVD scope
        regen_dates = regenerate_daily_metrics(db, days=max(1, int(recompute_days)))
        return CleanupResult(
            run_id=int(run.id),
            dry_run=False,
            target_count=target_count,
            archived_count=archived_count,
            deleted_count=deleted_count,
            recomputed_days=len(regen_dates),
            notes={'mode': 'execute', 'recomputed_days': len(regen_dates)},
        )
    except Exception:
        db.rollback()
        raise


def rollback_non_ivd_cleanup(
    db: Session,
    *,
    archive_batch_id: str,
    dry_run: bool,
    recompute_days: int = 365,
) -> RollbackResult:
    batch_id = str(archive_batch_id or '').strip()
    if not batch_id:
        raise RuntimeError('archive_batch_id is required')

    target_count = int(
        db.execute(
            text("SELECT COUNT(1) FROM products_archive WHERE archive_batch_id = :bid"),
            {'bid': batch_id},
        ).scalar()
        or 0
    )
    if dry_run:
        return RollbackResult(
            archive_batch_id=batch_id,
            dry_run=True,
            target_count=target_count,
            restored_count=0,
            skipped_existing=0,
        )

    restored = int(
        db.execute(
            text(
                """
                INSERT INTO products (
                    id, udi_di, reg_no, name, class, approved_date, expiry_date,
                    model, specification, category, status,
                    is_ivd, ivd_category, ivd_subtypes, ivd_reason, ivd_version,
                    ivd_source, ivd_confidence, company_id, registration_id, raw_json, raw, created_at, updated_at
                )
                SELECT
                    a.id, a.udi_di, a.reg_no, a.name, a.class, a.approved_date, a.expiry_date,
                    a.model, a.specification, a.category, a.status,
                    a.is_ivd, a.ivd_category, a.ivd_subtypes, a.ivd_reason, a.ivd_version,
                    NULL, NULL, a.company_id, a.registration_id, a.raw_json, a.raw, a.created_at, a.updated_at
                FROM products_archive a
                WHERE a.archive_batch_id = :bid
                  AND NOT EXISTS (
                    SELECT 1 FROM products p
                    WHERE p.id = a.id OR p.udi_di = a.udi_di
                  )
                """
            ),
            {'bid': batch_id},
        ).rowcount
        or 0
    )

    # Restore change_log evidence for this batch (best-effort, idempotent).
    db.execute(
        text(
            """
            INSERT INTO change_log (
                id, product_id, entity_type, entity_id, change_type,
                changed_fields, before_json, after_json, before_raw, after_raw,
                source_run_id, changed_at, change_date
            )
            SELECT
                a.id, a.product_id, a.entity_type, a.entity_id, a.change_type,
                COALESCE(a.changed_fields, '{}'::jsonb), a.before_json, a.after_json, a.before_raw, a.after_raw,
                a.source_run_id,
                COALESCE(a.changed_at, a.change_date, now()),
                COALESCE(a.change_date, a.changed_at, now())
            FROM change_log_archive a
            WHERE a.archive_batch_id = :bid
              AND a.id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM change_log c
                WHERE c.id = a.id
              )
            """
        ),
        {'bid': batch_id},
    )

    # Ensure change_log id sequence is ahead of restored ids.
    db.execute(
        text(
            """
            DO $$
            DECLARE
              seq text;
              mx bigint;
            BEGIN
              seq := pg_get_serial_sequence('change_log', 'id');
              IF seq IS NULL THEN
                RETURN;
              END IF;
              SELECT COALESCE(MAX(id), 0) INTO mx FROM change_log;
              PERFORM setval(seq, GREATEST(mx, 1), true);
            END $$;
            """
        )
    )
    db.commit()
    # Keep dashboard scope consistent after rollback.
    try:
        regenerate_daily_metrics(db, days=max(1, int(recompute_days)))
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    skipped = max(0, target_count - restored)
    return RollbackResult(
        archive_batch_id=batch_id,
        dry_run=False,
        target_count=target_count,
        restored_count=restored,
        skipped_existing=skipped,
    )
