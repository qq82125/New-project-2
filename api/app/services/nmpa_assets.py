from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChangeLog, FieldDiff, NmpaSnapshot, RawDocument, Registration
from app.services.mapping import ProductRecord
from app.services.source_contract import upsert_registration_with_contract

logger = logging.getLogger(__name__)


DIFF_FIELDS: tuple[str, ...] = (
    "registration_no",
    "filing_no",
    "approval_date",
    "expiry_date",
    "status",
    "product_name",
    "class",
    "model",
    "specification",
)

_SEVERITY: dict[str, str] = {
    "registration_no": "HIGH",
    "status": "HIGH",
    "expiry_date": "HIGH",
    "approval_date": "MED",
    "filing_no": "MED",
    "product_name": "MED",
    "class": "MED",
    "model": "LOW",
    "specification": "LOW",
}

_FILING_ALIASES = ("filing_no", "备案号", "备案凭证编号", "filingNo", "filingNO")
_MODEL_ALIASES = ("model", "型号", "xh", "xhao")
_SPEC_ALIASES = ("specification", "规格", "gg", "guige")


def _pick(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = raw.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _to_text(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _change_type_for(before: dict[str, Any], after: dict[str, Any]) -> str:
    # Keep it simple and stable; fine-tune later.
    if not before:
        return "REGISTER"
    old_status = str(before.get("status") or "").lower()
    new_status = str(after.get("status") or "").lower()
    if old_status != "cancelled" and new_status == "cancelled":
        return "CANCEL"
    old_exp = _parse_iso_date(_to_text(before.get("expiry_date")))
    new_exp = _parse_iso_date(_to_text(after.get("expiry_date")))
    if old_exp and new_exp and new_exp > old_exp:
        return "RENEW"
    return "MODIFY"


@dataclass
class ShadowWriteResult:
    ok: bool
    snapshot_id: Optional[UUID] = None
    diffs_written: int = 0
    error: str | None = None


def shadow_write_nmpa_snapshot_and_diffs(
    db: Session,
    *,
    record: ProductRecord,
    product_before: dict[str, Any] | None,
    product_after: dict[str, Any] | None,
    source_run_id: int | None,
    raw_document_id: UUID | None,
) -> ShadowWriteResult:
    reg_no = str(record.reg_no or "").strip()
    if not reg_no:
        return ShadowWriteResult(ok=False, error="missing reg_no (registration_no)")

    # Upsert registrations with source-contract conflict resolver.
    reg_before_obj = db.scalar(select(Registration).where(Registration.registration_no == reg_no))
    reg_before: dict[str, Any] = {}
    if reg_before_obj is not None:
        reg_before = {
            "registration_no": reg_before_obj.registration_no,
            "filing_no": reg_before_obj.filing_no,
            "approval_date": _to_text(reg_before_obj.approval_date),
            "expiry_date": _to_text(reg_before_obj.expiry_date),
            "status": reg_before_obj.status,
        }

    reg_upsert = upsert_registration_with_contract(
        db,
        registration_no=reg_no,
        incoming_fields={
            "filing_no": (_pick(record.raw, _FILING_ALIASES) or None),
            "approval_date": record.approved_date,
            "expiry_date": record.expiry_date,
            "status": record.status,
        },
        source="NMPA_UDI",
        source_run_id=source_run_id,
        evidence_grade="A",
        source_priority=10,
        observed_at=datetime.now(timezone.utc),
        raw_source_record_id=None,
        raw_payload=dict(record.raw),
        write_change_log=False,  # keep existing nmpa_assets change_log behavior below
    )
    reg = db.get(Registration, reg_upsert.registration_id)
    if reg is None:
        return ShadowWriteResult(ok=False, error="registration upsert failed")

    # Requirement: query the previous snapshot for this registration (best-effort).
    # We don't store a full snapshot payload yet; the diff baseline comes from canonical tables.
    try:
        _ = db.scalar(
            select(NmpaSnapshot)
            .where(NmpaSnapshot.registration_id == reg.id)
            .order_by(NmpaSnapshot.snapshot_date.desc(), NmpaSnapshot.created_at.desc())
            .limit(1)
        )
    except Exception:
        pass

    # Build a minimal diff surface per SSOT (docs/nmpa_field_dictionary_v1_adapted.yaml).
    before_surface: dict[str, Any] = dict(reg_before)
    after_surface: dict[str, Any] = {
        "registration_no": reg.registration_no,
        "filing_no": _pick(record.raw, _FILING_ALIASES),
        "approval_date": _to_text(record.approved_date),
        "expiry_date": _to_text(record.expiry_date),
        "status": record.status,
        "product_name": record.name,
        "class": record.class_name,
        "model": _pick(record.raw, _MODEL_ALIASES),
        "specification": _pick(record.raw, _SPEC_ALIASES),
    }

    # Merge in product before/after if provided. Existing product change tracking doesn't include model/spec yet.
    if product_before:
        before_surface.setdefault("product_name", product_before.get("name"))
        before_surface.setdefault("class", product_before.get("class"))
    if product_after:
        after_surface.setdefault("product_name", product_after.get("name"))
        after_surface.setdefault("class", product_after.get("class"))

    # Insert snapshot (idempotent per registration_id+source_run_id).
    src_url = None
    sha256 = None
    if raw_document_id is not None:
        try:
            doc = db.get(RawDocument, raw_document_id)
            if doc is not None:
                src_url = doc.source_url
                sha256 = doc.sha256
        except Exception:
            pass

    snap_stmt = insert(NmpaSnapshot).values(
        registration_id=reg.id,
        raw_document_id=raw_document_id,
        source_run_id=source_run_id,
        snapshot_date=date.today(),
        source_url=src_url,
        sha256=sha256,
    )
    snap_stmt = snap_stmt.on_conflict_do_update(
        index_elements=[NmpaSnapshot.registration_id, NmpaSnapshot.source_run_id],
        set_={
            "raw_document_id": snap_stmt.excluded.raw_document_id,
            "snapshot_date": snap_stmt.excluded.snapshot_date,
            "source_url": snap_stmt.excluded.source_url,
            "sha256": snap_stmt.excluded.sha256,
        },
    ).returning(NmpaSnapshot.id)
    snapshot_id = db.execute(snap_stmt).scalar_one()

    changed: dict[str, dict[str, Any]] = {}
    for f in DIFF_FIELDS:
        old = _to_text(before_surface.get(f))
        new = _to_text(after_surface.get(f))
        if old != new:
            changed[f] = {"old": old, "new": new}

    if not changed:
        return ShadowWriteResult(ok=True, snapshot_id=snapshot_id, diffs_written=0)

    change_type = _change_type_for(before_surface, after_surface)

    # Write field_diffs (best-effort, keep write simple).
    rows = []
    for field_name, v in changed.items():
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "registration_id": reg.id,
                "field_name": field_name,
                "old_value": v.get("old"),
                "new_value": v.get("new"),
                "change_type": change_type,
                "severity": _SEVERITY.get(field_name, "LOW"),
                "confidence": 0.80,
                "source_run_id": source_run_id,
            }
        )
    if rows:
        db.execute(insert(FieldDiff), rows)

    # Optional: align with existing change_log chain, but keep it additive and compatible.
    try:
        db.add(
            ChangeLog(
                product_id=None,
                entity_type="registration",
                entity_id=reg.id,
                change_type=("new" if (not reg_before) else "update"),
                changed_fields=changed,
                before_json=before_surface or None,
                after_json=after_surface or None,
                before_raw=None,
                after_raw=dict(record.raw),
                source_run_id=source_run_id,
            )
        )
    except Exception:
        # Never block the main ingest for change_log alignment.
        pass

    return ShadowWriteResult(ok=True, snapshot_id=snapshot_id, diffs_written=len(rows))


def record_shadow_diff_failure(
    db: Session,
    *,
    raw_document_id: UUID | None,
    source_run_id: int | None,
    registration_no: str | None,
    error: str,
) -> None:
    """Best-effort: append a diff failure record into raw_documents.parse_log.

    This must never block the main ingest transaction. Callers should already be in a try/except.
    """
    if raw_document_id is None:
        return
    doc = db.get(RawDocument, raw_document_id)
    if doc is None:
        return
    payload = doc.parse_log if isinstance(doc.parse_log, dict) else {}
    errors = payload.get("shadow_diff_errors")
    if not isinstance(errors, list):
        errors = []
    errors.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source_run_id": int(source_run_id) if source_run_id is not None else None,
            "registration_no": (str(registration_no).strip() or None) if registration_no else None,
            "error": str(error),
        }
    )
    # Cap to avoid unbounded growth for a single package document.
    if len(errors) > 50:
        errors = errors[-50:]
    payload["shadow_diff_errors"] = errors
    doc.parse_log = payload
    db.add(doc)
