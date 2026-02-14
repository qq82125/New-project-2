from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import SourceRun
from app.repositories.source_runs import finish_source_run, start_source_run


def create_run(db: Session, source: str) -> str:
    # Back-compat wrapper (prefer repositories.source_runs or pipeline.source_run_context).
    run = start_source_run(db, source=source, package_name=None, package_md5=None, download_url=None)
    return f'source_run:{int(run.id)}'


def finish_run(db: Session, run_id: str, *, stats: dict[str, Any], errors: list[str] | None = None) -> None:
    _, _, raw_id = str(run_id).partition(':')
    try:
        run_numeric_id = int(raw_id)
    except Exception:
        return
    run = db.get(SourceRun, run_numeric_id)
    if not run:
        return
    # Normalize to existing status strings used elsewhere ('success'/'failed').
    status = 'failed' if errors else 'success'
    message = '; '.join(errors or [])[:1000] if errors else 'ok'
    finish_source_run(
        db,
        run,
        status=status,
        message=message,
        records_total=int(stats.get('fetched_count', 0) or 0),
        records_success=int(stats.get('parsed_count', 0) or 0),
        records_failed=int(stats.get('failed_count', 0) or 0),
        added_count=int(stats.get('added', 0) or 0),
        updated_count=int(stats.get('updated', 0) or 0),
        removed_count=int(stats.get('removed', 0) or 0),
        source_notes={
            'pipeline': True,
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'stats': stats,
            'errors': errors or [],
        },
    )
