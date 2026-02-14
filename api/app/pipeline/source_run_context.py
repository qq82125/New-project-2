from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.models import SourceRun
from app.repositories.source_runs import finish_source_run, start_source_run


@contextmanager
def source_run(
    db: Session,
    *,
    source: str,
    package_name: str | None = None,
    package_md5: str | None = None,
    download_url: str | None = None,
    source_notes: dict[str, Any] | None = None,
) -> Iterator[tuple[SourceRun, str, dict[str, Any]]]:
    """Run-scoped helper for sources.

    Conventions:
    - Raw evidence chain uses raw_documents.run_id == f"source_run:{run.id}".
    - Callers should update the yielded stats dict with:
      fetched_count, parsed_count, failed_count, added, updated, removed, duration_seconds, etc.
    """
    run = start_source_run(
        db,
        source=source,
        package_name=package_name,
        package_md5=package_md5,
        download_url=download_url,
    )
    raw_run_id = f"source_run:{int(run.id)}"
    stats: dict[str, Any] = {}
    started = datetime.now(timezone.utc)
    try:
        yield run, raw_run_id, stats
    except Exception as exc:
        # Best-effort failure close. Caller can still override by calling finish_source_run themselves,
        # but the recommended pattern is to rely on this context manager.
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        stats.setdefault("duration_seconds", duration)
        finish_source_run(
            db,
            run,
            status="failed",
            message=str(exc),
            records_total=int(stats.get("fetched_count", 0) or 0),
            records_success=int(stats.get("parsed_count", 0) or 0),
            records_failed=int(stats.get("failed_count", 0) or 0),
            added_count=int(stats.get("added", 0) or 0),
            updated_count=int(stats.get("updated", 0) or 0),
            removed_count=int(stats.get("removed", 0) or 0),
            source_notes={"stats": stats, **(source_notes or {})},
        )
        raise
    else:
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        stats.setdefault("duration_seconds", duration)
        finish_source_run(
            db,
            run,
            status="success",
            message="ok",
            records_total=int(stats.get("fetched_count", 0) or 0),
            records_success=int(stats.get("parsed_count", 0) or 0),
            records_failed=int(stats.get("failed_count", 0) or 0),
            added_count=int(stats.get("added", 0) or 0),
            updated_count=int(stats.get("updated", 0) or 0),
            removed_count=int(stats.get("removed", 0) or 0),
            source_notes={"stats": stats, **(source_notes or {})},
        )

