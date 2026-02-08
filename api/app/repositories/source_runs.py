from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import SourceRun


def start_source_run(
    db: Session,
    source: str,
    package_name: str | None,
    package_md5: str | None,
    download_url: str | None,
) -> SourceRun:
    run = SourceRun(
        source=source,
        package_name=package_name,
        package_md5=package_md5,
        download_url=download_url,
        status='RUNNING',
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_source_run(
    db: Session,
    run: SourceRun,
    status: str,
    message: str | None,
    records_total: int,
    records_success: int,
    records_failed: int,
    added_count: int = 0,
    updated_count: int = 0,
    removed_count: int = 0,
) -> SourceRun:
    run.status = status
    run.message = message
    run.records_total = records_total
    run.records_success = records_success
    run.records_failed = records_failed
    run.added_count = added_count
    run.updated_count = updated_count
    run.removed_count = removed_count
    run.finished_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def latest_runs(db: Session, limit: int = 10) -> list[SourceRun]:
    stmt = select(SourceRun).order_by(desc(SourceRun.started_at)).limit(limit)
    return list(db.scalars(stmt))


def list_source_runs(db: Session, limit: int = 50) -> list[SourceRun]:
    stmt = select(SourceRun).order_by(desc(SourceRun.started_at)).limit(limit)
    return list(db.scalars(stmt))
