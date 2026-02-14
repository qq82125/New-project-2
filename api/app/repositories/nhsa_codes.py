from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import NhsaCode


@dataclass(frozen=True)
class NhsaUpsertResult:
    total: int
    upserted: int


def upsert_nhsa_codes(
    db: Session,
    *,
    rows: list[dict[str, Any]],
    snapshot_month: str,
    raw_document_id: UUID,
    source_run_id: int,
    dry_run: bool,
) -> NhsaUpsertResult:
    total = len(rows)
    if dry_run or not rows:
        return NhsaUpsertResult(total=total, upserted=0)

    values: list[dict[str, Any]] = []
    for r in rows:
        code = str(r.get('code') or '').strip()
        if not code:
            continue
        values.append(
            {
                'code': code,
                'snapshot_month': snapshot_month,
                'name': (str(r.get('name')).strip() if r.get('name') is not None else None),
                'spec': (str(r.get('spec')).strip() if r.get('spec') is not None else None),
                'manufacturer': (str(r.get('manufacturer')).strip() if r.get('manufacturer') is not None else None),
                'raw': dict(r.get('raw') or {}),
                'raw_document_id': raw_document_id,
                'source_run_id': int(source_run_id),
            }
        )

    if not values:
        return NhsaUpsertResult(total=total, upserted=0)

    stmt = insert(NhsaCode).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[NhsaCode.code, NhsaCode.snapshot_month],
        set_={
            'name': stmt.excluded.name,
            'spec': stmt.excluded.spec,
            'manufacturer': stmt.excluded.manufacturer,
            'raw': stmt.excluded.raw,
            'raw_document_id': stmt.excluded.raw_document_id,
            'source_run_id': stmt.excluded.source_run_id,
        },
    )
    db.execute(stmt)
    db.commit()
    return NhsaUpsertResult(total=total, upserted=len(values))


def rollback_nhsa_codes_by_source_run(
    db: Session,
    *,
    source_run_id: int,
    dry_run: bool,
) -> int:
    if dry_run:
        stmt = select(func.count()).select_from(NhsaCode).where(NhsaCode.source_run_id == int(source_run_id))
        return int(db.scalar(stmt) or 0)
    stmt = delete(NhsaCode).where(NhsaCode.source_run_id == int(source_run_id))
    res = db.execute(stmt)
    db.commit()
    return int(res.rowcount or 0)
