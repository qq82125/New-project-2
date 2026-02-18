#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from uuid import UUID
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.services.udi_promote import promote_udi_from_device_index  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(float(value) * 100.0 / float(total), 2)


def run_snapshot(
    *,
    source_run_id: int | None,
    raw_document_id: str | None,
    source: str,
    limit: int | None,
    execute: bool,
) -> dict[str, Any]:
    rid = UUID(raw_document_id) if raw_document_id else None
    db = SessionLocal()
    try:
        report = promote_udi_from_device_index(
            db,
            source_run_id=source_run_id,
            raw_document_id=rid,
            source=source,
            dry_run=not execute,
            limit=limit,
        )
        payload = asdict(report)
        scanned = int(payload.get("scanned", 0) or 0)
        with_registration = int(payload.get("with_registration_no", 0) or 0)
        missing = int(payload.get("missing_registration_no", 0) or 0)
        pending = int(payload.get("pending_written", 0) or 0)
        promoted = int(payload.get("promoted", 0) or 0)
        failed = int(payload.get("failed", 0) or 0)

        payload["snapshot"] = {
            "generated_at": _utc_now(),
            "source": source,
            "source_run_id": source_run_id,
            "raw_document_id": raw_document_id,
            "execute": bool(execute),
            "limit": limit,
            "metrics": {
                "promoted_rate_pct": _safe_float(promoted, scanned),
                "reg_no_hit_rate_pct": _safe_float(with_registration, scanned),
                "missing_reg_no_rate_pct": _safe_float(missing, scanned),
                "pending_rate_pct": _safe_float(pending, scanned),
                "failure_rate_pct": _safe_float(failed, scanned),
                "with_registration_no": with_registration,
                "missing_registration_no": missing,
                "pending_written": pending,
                "failed": failed,
            },
        }
        return payload
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UDI promote snapshot runner for monitoring and retry control.")
    p.add_argument("--source-run-id", type=int, help="Filter udi_device_index by source_runs.id")
    p.add_argument("--raw-document-id", help="Filter udi_device_index by raw_documents.id")
    p.add_argument("--source", default="UDI_PROMOTE", help="Source label for upsert/pending paths (default: UDI_PROMOTE)")
    p.add_argument("--limit", type=int, default=None, help="Optional max rows to process")
    p.add_argument("--execute", action="store_true", help="Persist writes (default is dry-run)")
    return p


def main() -> None:
    args = build_parser().parse_args()
    result = run_snapshot(
        source_run_id=args.source_run_id,
        raw_document_id=args.raw_document_id,
        source=args.source,
        limit=args.limit,
        execute=bool(args.execute),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
