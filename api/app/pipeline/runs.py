from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import SourceRun


def create_run(db: Session, source: str) -> str:
    run = SourceRun(
        source=source,
        status='RUNNING',
        message='started by pipeline',
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return f'{source}:{run.id}'


def finish_run(db: Session, run_id: str, *, stats: dict[str, Any], errors: list[str] | None = None) -> None:
    source, _, raw_id = str(run_id).partition(':')
    try:
        run_numeric_id = int(raw_id)
    except Exception:
        return
    run = db.get(SourceRun, run_numeric_id)
    if not run:
        return
    run.status = 'FAILED' if errors else 'SUCCESS'
    run.finished_at = datetime.now(timezone.utc)
    run.records_total = int(stats.get('fetched_count', 0))
    run.records_success = int(stats.get('parsed_count', 0))
    run.records_failed = int(stats.get('failed_count', 0))
    run.message = '; '.join(errors or [])[:1000] if errors else 'ok'
    run.source_notes = {'pipeline_source': source, 'stats': stats, 'errors': errors or []}
    db.add(run)
    db.commit()
