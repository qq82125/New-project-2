from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DatasetRef:
    id: str
    dataset_version: str
    source_key: str
    rows_written: int
    rows_failed: int


@dataclass(frozen=True)
class DatasetFileEntry:
    relative_path: str
    file_sha256: str
    file_size: int
    imported: bool
    skipped_reason: str | None
    rows_failed: int


def _resolve_dataset(db: Session, *, source_key: str, ref: str) -> DatasetRef:
    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("dataset ref is required")
    is_uuid = False
    try:
        uuid.UUID(raw)
        is_uuid = True
    except Exception:
        is_uuid = False

    if is_uuid:
        row = db.execute(
            text(
                """
                SELECT id::text, dataset_version, source_key, rows_written, rows_failed
                FROM offline_datasets
                WHERE source_key = :source_key
                  AND id = CAST(:ref AS uuid)
                LIMIT 1
                """
            ),
            {"source_key": source_key, "ref": raw},
        ).first()
        if row:
            return DatasetRef(
                id=str(row[0]),
                dataset_version=str(row[1]),
                source_key=str(row[2]),
                rows_written=int(row[3] or 0),
                rows_failed=int(row[4] or 0),
            )

    row = db.execute(
        text(
            """
            SELECT id::text, dataset_version, source_key, rows_written, rows_failed
            FROM offline_datasets
            WHERE source_key = :source_key
              AND dataset_version = :ref
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"source_key": source_key, "ref": raw},
    ).first()
    if not row:
        raise ValueError(f"dataset not found for source_key={source_key}, ref={raw}")
    return DatasetRef(
        id=str(row[0]),
        dataset_version=str(row[1]),
        source_key=str(row[2]),
        rows_written=int(row[3] or 0),
        rows_failed=int(row[4] or 0),
    )


def _list_dataset_files(db: Session, *, dataset_id: str) -> list[DatasetFileEntry]:
    rows = db.execute(
        text(
            """
            SELECT
                relative_path,
                file_sha256,
                file_size,
                imported,
                skipped_reason,
                rows_failed
            FROM offline_dataset_files
            WHERE dataset_id = CAST(:dataset_id AS uuid)
            """
        ),
        {"dataset_id": dataset_id},
    ).fetchall()
    out: list[DatasetFileEntry] = []
    for r in rows:
        out.append(
            DatasetFileEntry(
                relative_path=str(r[0]),
                file_sha256=str(r[1]),
                file_size=int(r[2] or 0),
                imported=bool(r[3]),
                skipped_reason=(str(r[4]) if r[4] is not None else None),
                rows_failed=int(r[5] or 0),
            )
        )
    return out


def _top_reason_codes(db: Session, *, source_key: str, dataset_version: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                COALESCE(NULLIF(parse_error, ''), 'OK') AS reason_code,
                COUNT(*)::bigint AS cnt
            FROM raw_source_records
            WHERE source = :source_key
              AND payload->>'dataset_version' = :dataset_version
            GROUP BY 1
            ORDER BY cnt DESC, reason_code ASC
            LIMIT :limit
            """
        ),
        {"source_key": source_key, "dataset_version": dataset_version, "limit": int(limit)},
    ).fetchall()
    return [{"reason_code": str(r[0]), "count": int(r[1] or 0)} for r in rows]


def _count_reason_codes(db: Session, *, source_key: str, dataset_version: str) -> dict[str, int]:
    rows = db.execute(
        text(
            """
            SELECT
                COALESCE(NULLIF(parse_error, ''), 'OK') AS reason_code,
                COUNT(*)::bigint AS cnt
            FROM raw_source_records
            WHERE source = :source_key
              AND payload->>'dataset_version' = :dataset_version
            GROUP BY 1
            """
        ),
        {"source_key": source_key, "dataset_version": dataset_version},
    ).fetchall()
    return {str(r[0]): int(r[1] or 0) for r in rows}


def _top_failure_files(files: list[DatasetFileEntry], limit: int = 10) -> list[dict[str, Any]]:
    ranked = sorted(files, key=lambda x: (-int(x.rows_failed or 0), x.relative_path))
    out: list[dict[str, Any]] = []
    for f in ranked:
        if int(f.rows_failed or 0) <= 0:
            continue
        out.append(
            {
                "relative_path": f.relative_path,
                "rows_failed": int(f.rows_failed or 0),
                "file_sha256": f.file_sha256,
            }
        )
        if len(out) >= limit:
            break
    return out


def _file_maps(files: list[DatasetFileEntry]) -> dict[str, DatasetFileEntry]:
    # Same relative path should be unique per dataset. If duplicated unexpectedly, keep the latest appearance.
    return {f.relative_path: f for f in files}


def build_offline_dataset_diff(
    db: Session,
    *,
    source_key: str,
    from_ref: str,
    to_ref: str,
    persist: bool = True,
) -> dict[str, Any]:
    from_ds = _resolve_dataset(db, source_key=source_key, ref=from_ref)
    to_ds = _resolve_dataset(db, source_key=source_key, ref=to_ref)

    from_files = _list_dataset_files(db, dataset_id=from_ds.id)
    to_files = _list_dataset_files(db, dataset_id=to_ds.id)
    from_map = _file_maps(from_files)
    to_map = _file_maps(to_files)

    added_files: list[dict[str, Any]] = []
    removed_files: list[dict[str, Any]] = []
    unchanged_files: list[dict[str, Any]] = []
    changed_files: list[dict[str, Any]] = []

    for rel, f_to in to_map.items():
        f_from = from_map.get(rel)
        if f_from is None:
            added_files.append(
                {
                    "relative_path": rel,
                    "sha256": f_to.file_sha256,
                    "size": int(f_to.file_size),
                }
            )
            continue
        if f_from.file_sha256 == f_to.file_sha256:
            unchanged_files.append(
                {
                    "relative_path": rel,
                    "sha256": f_to.file_sha256,
                    "size": int(f_to.file_size),
                }
            )
        else:
            changed_files.append(
                {
                    "relative_path": rel,
                    "from_sha256": f_from.file_sha256,
                    "to_sha256": f_to.file_sha256,
                    "from_size": int(f_from.file_size),
                    "to_size": int(f_to.file_size),
                }
            )

    for rel, f_from in from_map.items():
        if rel in to_map:
            continue
        removed_files.append(
            {
                "relative_path": rel,
                "sha256": f_from.file_sha256,
                "size": int(f_from.file_size),
            }
        )

    dup_files_in_to = [
        {
            "relative_path": f.relative_path,
            "sha256": f.file_sha256,
            "size": int(f.file_size),
            "skipped_reason": str(f.skipped_reason or ""),
        }
        for f in to_files
        if str(f.skipped_reason or "").upper() == "DUP_SHA256"
    ]

    rows_written_delta = int(to_ds.rows_written - from_ds.rows_written)
    rows_failed_delta = int(to_ds.rows_failed - from_ds.rows_failed)

    top_failure_files_from = _top_failure_files(from_files, limit=10)
    top_failure_files_to = _top_failure_files(to_files, limit=10)

    top_reason_codes_from = _top_reason_codes(db, source_key=source_key, dataset_version=from_ds.dataset_version, limit=20)
    top_reason_codes_to = _top_reason_codes(db, source_key=source_key, dataset_version=to_ds.dataset_version, limit=20)
    reason_from = _count_reason_codes(db, source_key=source_key, dataset_version=from_ds.dataset_version)
    reason_to = _count_reason_codes(db, source_key=source_key, dataset_version=to_ds.dataset_version)
    reason_delta = {
        k: int(reason_to.get(k, 0) - reason_from.get(k, 0))
        for k in sorted(set(reason_from.keys()) | set(reason_to.keys()))
    }

    summary_json = {
        "added_files_count": len(added_files),
        "removed_files_count": len(removed_files),
        "unchanged_files_count": len(unchanged_files),
        "changed_files_count": len(changed_files),
        "dup_files_in_to_count": len(dup_files_in_to),
        "rows_written_delta": rows_written_delta,
        "rows_failed_delta": rows_failed_delta,
        "reason_code_delta_nonzero": {k: v for k, v in reason_delta.items() if int(v) != 0},
    }

    out: dict[str, Any] = {
        "source_key": source_key,
        "from_dataset": {
            "id": from_ds.id,
            "dataset_version": from_ds.dataset_version,
            "rows_written": int(from_ds.rows_written),
            "rows_failed": int(from_ds.rows_failed),
        },
        "to_dataset": {
            "id": to_ds.id,
            "dataset_version": to_ds.dataset_version,
            "rows_written": int(to_ds.rows_written),
            "rows_failed": int(to_ds.rows_failed),
        },
        "file_diff": {
            "added_files": sorted(added_files, key=lambda x: str(x["relative_path"])),
            "removed_files": sorted(removed_files, key=lambda x: str(x["relative_path"])),
            "unchanged_files": sorted(unchanged_files, key=lambda x: str(x["relative_path"])),
            "changed_files": sorted(changed_files, key=lambda x: str(x["relative_path"])),
            "dup_files_in_to": sorted(dup_files_in_to, key=lambda x: str(x["relative_path"])),
        },
        "row_diff": {
            "rows_written_delta": rows_written_delta,
            "rows_failed_delta": rows_failed_delta,
            "top_failure_files_from": top_failure_files_from,
            "top_failure_files_to": top_failure_files_to,
        },
        "reason_code_diff": {
            "top_reason_codes_from": top_reason_codes_from,
            "top_reason_codes_to": top_reason_codes_to,
            "delta": reason_delta,
        },
        "summary_json": summary_json,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    if persist:
        row = db.execute(
            text(
                """
                INSERT INTO offline_dataset_diffs (
                    source_key, from_dataset_id, to_dataset_id, summary_json, created_at
                ) VALUES (
                    :source_key, CAST(:from_dataset_id AS uuid), CAST(:to_dataset_id AS uuid), CAST(:summary_json AS jsonb), NOW()
                )
                RETURNING id::text
                """
            ),
            {
                "source_key": source_key,
                "from_dataset_id": from_ds.id,
                "to_dataset_id": to_ds.id,
                "summary_json": json.dumps(summary_json, ensure_ascii=False),
            },
        ).first()
        if row and row[0]:
            out["diff_id"] = str(row[0])
    return out


def format_offline_dataset_diff_text(diff: dict[str, Any]) -> str:
    f = diff.get("file_diff", {}) if isinstance(diff, dict) else {}
    r = diff.get("row_diff", {}) if isinstance(diff, dict) else {}
    rc = diff.get("reason_code_diff", {}) if isinstance(diff, dict) else {}
    lines: list[str] = []
    lines.append(f"source_key: {diff.get('source_key')}")
    lines.append(
        f"from: {diff.get('from_dataset', {}).get('dataset_version')} ({diff.get('from_dataset', {}).get('id')})"
    )
    lines.append(f"to:   {diff.get('to_dataset', {}).get('dataset_version')} ({diff.get('to_dataset', {}).get('id')})")
    lines.append("")
    lines.append("File Diff")
    lines.append(f"added_files: {len(f.get('added_files', []) or [])}")
    lines.append(f"removed_files: {len(f.get('removed_files', []) or [])}")
    lines.append(f"unchanged_files: {len(f.get('unchanged_files', []) or [])}")
    lines.append(f"changed_files: {len(f.get('changed_files', []) or [])}")
    lines.append(f"dup_files_in_to: {len(f.get('dup_files_in_to', []) or [])}")
    lines.append("")
    lines.append("Rows Diff")
    lines.append(f"rows_written_delta: {int(r.get('rows_written_delta') or 0)}")
    lines.append(f"rows_failed_delta: {int(r.get('rows_failed_delta') or 0)}")
    lines.append("top_failure_files_to:")
    for it in (r.get("top_failure_files_to") or [])[:10]:
        lines.append(f"  - {it.get('relative_path')} rows_failed={it.get('rows_failed')}")
    lines.append("")
    lines.append("Reason Code Diff (top)")
    lines.append("from:")
    for it in (rc.get("top_reason_codes_from") or [])[:10]:
        lines.append(f"  - {it.get('reason_code')}: {it.get('count')}")
    lines.append("to:")
    for it in (rc.get("top_reason_codes_to") or [])[:10]:
        lines.append(f"  - {it.get('reason_code')}: {it.get('count')}")
    return "\n".join(lines)
