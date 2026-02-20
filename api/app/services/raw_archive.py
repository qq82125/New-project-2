from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ArchiveEstimate:
    documents_count: int
    source_records_count: int
    documents_estimated_bytes: int
    source_records_estimated_bytes: int

    @property
    def total_count(self) -> int:
        return int(self.documents_count) + int(self.source_records_count)

    @property
    def total_estimated_bytes(self) -> int:
        return int(self.documents_estimated_bytes) + int(self.source_records_estimated_bytes)


@dataclass
class ArchiveReport:
    dry_run: bool
    older_than_days: int
    cutoff_at: str
    estimate: ArchiveEstimate
    updated_documents: int = 0
    updated_source_records: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "dry_run": bool(self.dry_run),
            "older_than_days": int(self.older_than_days),
            "cutoff_at": self.cutoff_at,
            "estimated": {
                "documents_count": int(self.estimate.documents_count),
                "source_records_count": int(self.estimate.source_records_count),
                "total_count": int(self.estimate.total_count),
                "documents_bytes": int(self.estimate.documents_estimated_bytes),
                "source_records_bytes": int(self.estimate.source_records_estimated_bytes),
                "total_bytes": int(self.estimate.total_estimated_bytes),
            },
            "updated": {
                "documents": int(self.updated_documents),
                "source_records": int(self.updated_source_records),
            },
        }


def parse_older_than_days(raw: str) -> int:
    text0 = str(raw or "").strip().lower()
    if not text0:
        raise ValueError("older-than is required")
    if text0.endswith("d"):
        text0 = text0[:-1].strip()
    try:
        days = int(text0)
    except Exception as exc:
        raise ValueError(f"invalid --older-than: {raw}") from exc
    if days <= 0:
        raise ValueError("--older-than must be > 0")
    return days


def _estimate(db: Session, *, cutoff_at: datetime) -> ArchiveEstimate:
    doc_row = (
        db.execute(
            text(
                """
                SELECT
                  COUNT(1) AS cnt,
                  COALESCE(
                    SUM(COALESCE(pg_column_size(parse_log)::bigint, 0) + COALESCE(pg_column_size(error)::bigint, 0)),
                    0
                  ) AS bytes
                FROM raw_documents
                WHERE fetched_at < :cutoff
                  AND COALESCE(archive_status, 'active') <> 'archived'
                """
            ),
            {"cutoff": cutoff_at},
        )
        .mappings()
        .first()
        or {}
    )
    src_row = (
        db.execute(
            text(
                """
                SELECT
                  COUNT(1) AS cnt,
                  COALESCE(
                    SUM(COALESCE(pg_column_size(payload)::bigint, 0) + COALESCE(pg_column_size(parse_error)::bigint, 0)),
                    0
                  ) AS bytes
                FROM raw_source_records
                WHERE observed_at < :cutoff
                  AND COALESCE(archive_status, 'active') <> 'archived'
                """
            ),
            {"cutoff": cutoff_at},
        )
        .mappings()
        .first()
        or {}
    )
    return ArchiveEstimate(
        documents_count=int(doc_row.get("cnt") or 0),
        source_records_count=int(src_row.get("cnt") or 0),
        documents_estimated_bytes=int(doc_row.get("bytes") or 0),
        source_records_estimated_bytes=int(src_row.get("bytes") or 0),
    )


def archive_raw_data(db: Session, *, older_than_days: int, dry_run: bool) -> ArchiveReport:
    days = int(older_than_days)
    now = datetime.now(timezone.utc)
    cutoff_at = now - timedelta(days=days)
    estimate = _estimate(db, cutoff_at=cutoff_at)

    report = ArchiveReport(
        dry_run=bool(dry_run),
        older_than_days=days,
        cutoff_at=cutoff_at.isoformat(),
        estimate=estimate,
    )
    if dry_run:
        return report

    doc_res = db.execute(
        text(
            """
            UPDATE raw_documents
            SET
              parse_log = jsonb_build_object(
                'archived', true,
                'archived_at', NOW(),
                'retention_days', :days,
                'trace', jsonb_build_object('source', source, 'run_id', run_id, 'sha256', sha256)
              ),
              error = NULL,
              archive_status = 'archived',
              archived_at = NOW(),
              archive_note = :note
            WHERE fetched_at < :cutoff
              AND COALESCE(archive_status, 'active') <> 'archived'
            """
        ),
        {
            "days": days,
            "cutoff": cutoff_at,
            "note": f"retention>{days}d archived by ops:archive-raw",
        },
    )

    src_res = db.execute(
        text(
            """
            UPDATE raw_source_records
            SET
              payload = NULL,
              parse_error = NULL,
              archive_status = 'archived',
              archived_at = NOW(),
              archive_note = :note
            WHERE observed_at < :cutoff
              AND COALESCE(archive_status, 'active') <> 'archived'
            """
        ),
        {
            "cutoff": cutoff_at,
            "note": f"retention>{days}d archived by ops:archive-raw",
        },
    )

    report.updated_documents = int(doc_res.rowcount or 0)
    report.updated_source_records = int(src_res.rowcount or 0)
    db.commit()
    return report
