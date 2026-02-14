from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import requests
from sqlalchemy.orm import Session

from app.models import RawDocument
from app.pipeline.ingest import save_raw_document
from app.pipeline.source_run_context import source_run
from app.repositories.nhsa_codes import NhsaUpsertResult, rollback_nhsa_codes_by_source_run, upsert_nhsa_codes
from app.sources.nhsa.parser import parse_nhsa_csv


_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


@dataclass(frozen=True)
class NhsaIngestResult:
    source_run_id: int
    raw_run_id: str
    raw_document_id: UUID
    snapshot_month: str
    fetched_count: int
    parsed_count: int
    failed_count: int
    upserted: int


def _normalize_month(month: str) -> str:
    m = (month or "").strip()
    if not _MONTH_RE.match(m):
        raise ValueError(f"invalid --month (expected YYYY-MM): {month!r}")
    mm = int(m.split("-", 1)[1])
    if mm < 1 or mm > 12:
        raise ValueError(f"invalid --month (expected YYYY-MM with 01-12): {month!r}")
    return m


def _map_nhsa_row(row: dict[str, Any]) -> dict[str, Any]:
    # Keep mapping permissive; preserve full raw row for traceability.
    code = (
        row.get("code")
        or row.get("医保耗材编码")
        or row.get("国家医保耗材编码")
        or row.get("耗材编码")
        or row.get("编码")
        or row.get("CODE")
    )
    name = row.get("name") or row.get("通用名") or row.get("产品名称") or row.get("名称") or row.get("NAME")
    spec = (
        row.get("spec")
        or row.get("规格")
        or row.get("规格型号")
        or row.get("型号规格")
        or row.get("SPEC")
    )
    manufacturer = (
        row.get("manufacturer")
        or row.get("生产企业")
        or row.get("生产厂家")
        or row.get("生产企业名称")
        or row.get("企业名称")
        or row.get("MANUFACTURER")
    )
    return {
        "code": (str(code).strip() if code is not None else ""),
        "name": (str(name).strip() if name is not None else None),
        "spec": (str(spec).strip() if spec is not None else None),
        "manufacturer": (str(manufacturer).strip() if manufacturer is not None else None),
        "raw": dict(row),
    }


def ingest_nhsa_snapshot(
    db: Session,
    *,
    snapshot_month: str,
    content: bytes,
    source_url: str | None,
    doc_type: str = "csv",
    dry_run: bool,
) -> NhsaIngestResult:
    """Ingest one NHSA snapshot (month-level), with evidence chain in raw_documents.

    - Always writes raw_documents (even in dry_run) to keep an auditable evidence chain.
    - Structured writes go to nhsa_codes (unique per (code, snapshot_month)).
    """
    month = _normalize_month(snapshot_month)

    with source_run(db, source="nhsa", download_url=source_url, source_notes={"snapshot_month": month, "dry_run": bool(dry_run)}) as (
        run,
        raw_run_id,
        stats,
    ):
        raw_document_id = save_raw_document(
            db,
            source="NHSA",
            url=source_url,
            content=content,
            doc_type=doc_type,
            run_id=raw_run_id,
        )

        fetched_count = 1
        failed_count = 0
        parsed_rows: list[dict[str, Any]] = []
        try:
            rows = parse_nhsa_csv(content)
            parsed_rows = [_map_nhsa_row(r) for r in rows]
        except Exception as exc:
            failed_count = 1
            doc = db.get(RawDocument, raw_document_id)
            if doc is not None:
                doc.parse_status = "FAILED"
                doc.error = str(exc)
                doc.parse_log = {
                    "kind": "nhsa_snapshot",
                    "snapshot_month": month,
                    "dry_run": bool(dry_run),
                    "error": str(exc),
                    "parsed_at": datetime.now(timezone.utc).isoformat(),
                }
                db.add(doc)
                db.commit()
            raise

        upsert_res: NhsaUpsertResult = upsert_nhsa_codes(
            db,
            rows=parsed_rows,
            snapshot_month=month,
            raw_document_id=raw_document_id,
            source_run_id=int(run.id),
            dry_run=bool(dry_run),
        )

        parsed_count = len(parsed_rows)
        doc = db.get(RawDocument, raw_document_id)
        if doc is not None:
            doc.parse_status = "PARSED"
            doc.parse_log = {
                "kind": "nhsa_snapshot",
                "snapshot_month": month,
                "dry_run": bool(dry_run),
                "rows_total": parsed_count,
                "rows_upserted": upsert_res.upserted,
                "source_run_id": int(run.id),
                "parsed_at": datetime.now(timezone.utc).isoformat(),
            }
            db.add(doc)
            db.commit()

        stats.update(
            {
                "fetched_count": fetched_count,
                "parsed_count": parsed_count,
                "failed_count": failed_count,
                "upserted": upsert_res.upserted,
            }
        )
        return NhsaIngestResult(
            source_run_id=int(run.id),
            raw_run_id=raw_run_id,
            raw_document_id=raw_document_id,
            snapshot_month=month,
            fetched_count=fetched_count,
            parsed_count=parsed_count,
            failed_count=failed_count,
            upserted=upsert_res.upserted,
        )


def ingest_nhsa_from_url(
    db: Session,
    *,
    snapshot_month: str,
    url: str,
    timeout_seconds: int = 30,
    dry_run: bool,
) -> NhsaIngestResult:
    resp = requests.get(url, timeout=max(5, int(timeout_seconds)))
    resp.raise_for_status()
    return ingest_nhsa_snapshot(
        db,
        snapshot_month=snapshot_month,
        content=resp.content,
        source_url=url,
        doc_type="csv",
        dry_run=dry_run,
    )


def ingest_nhsa_from_file(
    db: Session,
    *,
    snapshot_month: str,
    file_path: str | Path,
    dry_run: bool,
) -> NhsaIngestResult:
    p = Path(file_path)
    content = p.read_bytes()
    return ingest_nhsa_snapshot(
        db,
        snapshot_month=snapshot_month,
        content=content,
        source_url=str(p),
        doc_type=(p.suffix.lstrip(".").lower() or "csv"),
        dry_run=dry_run,
    )


def rollback_nhsa_ingest(
    db: Session,
    *,
    source_run_id: int,
    dry_run: bool,
) -> dict[str, Any]:
    deleted = rollback_nhsa_codes_by_source_run(db, source_run_id=int(source_run_id), dry_run=bool(dry_run))
    return {"source_run_id": int(source_run_id), "deleted": int(deleted), "dry_run": bool(dry_run)}
