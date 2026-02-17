from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import ProcurementLot, ProcurementProject, ProcurementRegistrationMap, ProcurementResult


@dataclass(frozen=True)
class ProcurementRollbackResult:
    source_run_id: int
    dry_run: bool
    projects: int
    lots: int
    results: int
    maps: int


def rollback_procurement_by_source_run(db: Session, *, source_run_id: int, dry_run: bool) -> ProcurementRollbackResult:
    project_ids = (
        select(ProcurementProject.id).where(ProcurementProject.source_run_id == int(source_run_id)).subquery()
    )
    lot_ids = select(ProcurementLot.id).where(ProcurementLot.project_id.in_(select(project_ids.c.id))).subquery()

    if dry_run:
        projects = int(
            db.scalar(
                select(func.count()).select_from(ProcurementProject).where(ProcurementProject.source_run_id == int(source_run_id))
            )
            or 0
        )
        lots = int(
            db.scalar(
                select(func.count()).select_from(ProcurementLot).where(ProcurementLot.project_id.in_(select(project_ids.c.id)))
            )
            or 0
        )
        results = int(
            db.scalar(
                select(func.count()).select_from(ProcurementResult).where(ProcurementResult.lot_id.in_(select(lot_ids.c.id)))
            )
            or 0
        )
        maps = int(
            db.scalar(
                select(func.count())
                .select_from(ProcurementRegistrationMap)
                .where(ProcurementRegistrationMap.lot_id.in_(select(lot_ids.c.id)))
            )
            or 0
        )
        return ProcurementRollbackResult(
            source_run_id=int(source_run_id),
            dry_run=True,
            projects=projects,
            lots=lots,
            results=results,
            maps=maps,
        )

    # Delete from leaves to roots.
    res_maps = db.execute(delete(ProcurementRegistrationMap).where(ProcurementRegistrationMap.lot_id.in_(select(lot_ids.c.id))))
    res_results = db.execute(delete(ProcurementResult).where(ProcurementResult.lot_id.in_(select(lot_ids.c.id))))
    res_lots = db.execute(delete(ProcurementLot).where(ProcurementLot.project_id.in_(select(project_ids.c.id))))
    res_projects = db.execute(delete(ProcurementProject).where(ProcurementProject.source_run_id == int(source_run_id)))
    db.commit()

    return ProcurementRollbackResult(
        source_run_id=int(source_run_id),
        dry_run=False,
        projects=int(res_projects.rowcount or 0),
        lots=int(res_lots.rowcount or 0),
        results=int(res_results.rowcount or 0),
        maps=int(res_maps.rowcount or 0),
    )


def upsert_manual_registration_map(
    db: Session,
    *,
    lot_id: UUID,
    registration_id: UUID,
    confidence: float,
) -> dict[str, Any]:
    """Upsert a single (lot_id, registration_id) mapping with match_type='manual'."""
    # Avoid importing insert from dialect here; keep this module lightweight.
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(ProcurementRegistrationMap).values(
        lot_id=lot_id,
        registration_id=registration_id,
        match_type='manual',
        confidence=float(confidence),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProcurementRegistrationMap.lot_id, ProcurementRegistrationMap.registration_id],
        set_={
            'match_type': 'manual',
            'confidence': float(confidence),
        },
    ).returning(ProcurementRegistrationMap)

    row = db.execute(stmt).scalar_one()
    db.commit()
    return {
        'id': str(row.id),
        'lot_id': str(row.lot_id),
        'registration_id': str(row.registration_id),
        'match_type': str(row.match_type),
        'confidence': float(getattr(row, 'confidence', 0.0) or 0.0),
        'created_at': getattr(row, 'created_at', None),
    }

