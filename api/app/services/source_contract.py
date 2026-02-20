from __future__ import annotations

import hashlib
import json
import copy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    ChangeLog,
    ConflictQueue,
    PendingUdiLink,
    Product,
    ProductUdiMap,
    RawSourceRecord,
    Registration,
    RegistrationConflictAudit,
    SourceConfig,
    SourceDefinition,
    UdiDiMaster,
)
from app.services.normalize_keys import normalize_registration_no
from app.services.registration_no_parser import parse_registration_no


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _payload_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _grade(v: str | None, default: str = "C") -> str:
    raw = str(v or default).strip().upper()
    return raw if raw in {"A", "B", "C", "D"} else default


def _parse_status_for(registration_no_norm: str | None, di: str | None, parse_error: str | None) -> str:
    if parse_error:
        return "FAILED"
    if not di:
        return "FAILED"
    if registration_no_norm:
        return "PARSED"
    return "PENDING_REG_NO"


def _json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Convert to JSON-safe dict for JSONB columns (datetime/date/decimal -> string).
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def _pick_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            s = str(payload[key]).strip()
            if s:
                return s
    return None


def _parse_bool_zh(v: Any) -> bool | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s in {"是", "Y", "YES", "True", "TRUE", "1"}:
        return True
    if s in {"否", "N", "NO", "False", "FALSE", "0"}:
        return False
    return None


def _parse_packaging_json(row: dict[str, Any]) -> dict[str, Any] | None:
    pre = row.get("packaging_json")
    if isinstance(pre, dict) and isinstance(pre.get("packings"), list):
        # Already canonical (from XML parser). Keep as-is.
        return pre
    raw = row.get("packingList")
    items: list[dict[str, Any]] = []
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, dict):
        raw = raw.get("packings") or raw.get("packing") or raw.get("items")
    if isinstance(raw, list):
        for it in raw:
            if not isinstance(it, dict):
                continue
            package_di = _pick_text(it, "bzcpbs", "package_di")
            if not package_di:
                continue
            items.append(
                {
                    "package_di": package_di,
                    "package_level": _pick_text(it, "cpbzjb", "package_level"),
                    "contains_qty": _pick_text(it, "bznhxyjcpbssl", "contains_qty"),
                    "child_di": _pick_text(it, "bznhxyjbzcpbs", "child_di"),
                }
            )
    if not items:
        return None
    return {"packings": items}


def _parse_storage_json(row: dict[str, Any]) -> dict[str, Any] | None:
    pre = row.get("storage_json")
    if isinstance(pre, dict) and isinstance(pre.get("storages"), list):
        # Already canonical (from XML parser). Keep as-is.
        return pre
    raw = row.get("storageList")
    items: list[dict[str, Any]] = []
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, dict):
        raw = raw.get("storages") or raw.get("storage") or raw.get("items")
    if isinstance(raw, list):
        for it in raw:
            if not isinstance(it, dict):
                continue
            t = _pick_text(it, "cchcztj", "type")
            mn = _pick_text(it, "zdz", "min")
            mx = _pick_text(it, "zgz", "max")
            unit = _pick_text(it, "jldw", "unit")
            if not any([t, mn, mx, unit]):
                continue
            rng = _pick_text(it, "range")
            if not rng:
                if mn and mx and unit:
                    rng = f"{mn}-{mx}{unit}"
                elif mn and mx:
                    rng = f"{mn}-{mx}"
                else:
                    rng = (mn or mx or "") + (unit or "")
                    rng = rng.strip() or None
            items.append({"type": t, "min": mn, "max": mx, "unit": unit, "range": rng})

    # Fallback: many UDI XML exports carry text storage conditions under <tscchcztj>.
    if not items:
        txt = _pick_text(row, "tscchcztj")
        if txt:
            items.append({"type": "TEXT", "range": txt})

    if not items:
        return None
    return {"storages": items}


_GRADE_RANK: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1}
_REG_FIELDS: tuple[str, ...] = ("filing_no", "approval_date", "expiry_date", "status")


def _as_text(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def _as_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _as_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            x = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return _utcnow()


def _field_meta_entry(
    *,
    source_key: str,
    incoming_meta: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    return {
        "source_key": str(incoming_meta.get("source_key") or source_key or "UNKNOWN"),
        "evidence_grade": str(incoming_meta.get("evidence_grade") or ""),
        "observed_at": str(incoming_meta.get("observed_at") or ""),
        "raw_id": (str(incoming_meta.get("raw_source_record_id")) if incoming_meta.get("raw_source_record_id") else None),
        "decision": str(decision or "unknown"),
        "updated_at": _utcnow().isoformat(),
    }


def _decision_tuple(meta: dict[str, Any]) -> tuple[int, int, datetime]:
    grade = _grade(str(meta.get("evidence_grade") or "D"), default="D")
    try:
        priority = int(meta.get("source_priority") if meta.get("source_priority") is not None else 10_000)
    except Exception:
        priority = 10_000
    observed_at = _as_dt(meta.get("observed_at"))
    # Higher is better for all tuple positions.
    return (_GRADE_RANK.get(grade, 1), -priority, observed_at)


def _meta_sort(meta: dict[str, Any] | None) -> tuple[int, int, datetime]:
    if not isinstance(meta, dict):
        return (0, -10_000, datetime(1970, 1, 1, tzinfo=timezone.utc))
    return _decision_tuple(meta)


def _same_rank(existing_meta: dict[str, Any] | None, incoming_meta: dict[str, Any]) -> bool:
    em = _meta_sort(existing_meta)
    im = _meta_sort(incoming_meta)
    return em[0] == im[0] and em[1] == im[1]


def _same_observed_at(existing_meta: dict[str, Any] | None, incoming_meta: dict[str, Any]) -> bool:
    eo = _as_dt((existing_meta or {}).get("observed_at") if isinstance(existing_meta, dict) else None)
    io = _as_dt(incoming_meta.get("observed_at"))
    return eo == io


def _should_take(existing_meta: dict[str, Any] | None, incoming_meta: dict[str, Any]) -> bool:
    if not isinstance(existing_meta, dict) or not existing_meta:
        return True
    return _decision_tuple(incoming_meta) >= _decision_tuple(existing_meta)


def _reject_reason(existing_meta: dict[str, Any] | None, incoming_meta: dict[str, Any]) -> str:
    if not isinstance(existing_meta, dict) or not existing_meta:
        return "no_existing_meta"
    eg = _GRADE_RANK.get(_grade(str(existing_meta.get("evidence_grade") or "D"), default="D"), 1)
    ig = _GRADE_RANK.get(_grade(str(incoming_meta.get("evidence_grade") or "D"), default="D"), 1)
    if ig < eg:
        return "lower_evidence_grade"
    try:
        ep = int(existing_meta.get("source_priority") if existing_meta.get("source_priority") is not None else 10_000)
    except Exception:
        ep = 10_000
    try:
        ip = int(incoming_meta.get("source_priority") if incoming_meta.get("source_priority") is not None else 10_000)
    except Exception:
        ip = 10_000
    if ig == eg and ip > ep:
        return "lower_source_priority"
    eo = _as_dt(existing_meta.get("observed_at"))
    io = _as_dt(incoming_meta.get("observed_at"))
    if ig == eg and ip == ep and io < eo:
        return "older_observed_at"
    return "tie_break_lost"


def _queue_conflict_candidates(
    *,
    old_value: str | None,
    incoming_value: str | None,
    existing_meta: dict[str, Any] | None,
    incoming_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if old_value is not None:
        out.append(
            {
                "source_key": str((existing_meta or {}).get("source_key") or (existing_meta or {}).get("source") or "UNKNOWN"),
                "value": old_value,
                "raw_id": ((existing_meta or {}).get("raw_source_record_id") if isinstance(existing_meta, dict) else None),
                "observed_at": str((existing_meta or {}).get("observed_at") or ""),
                "evidence_grade": str((existing_meta or {}).get("evidence_grade") or ""),
                "source_priority": (existing_meta or {}).get("source_priority") if isinstance(existing_meta, dict) else None,
            }
        )
    if incoming_value is not None:
        out.append(
            {
                "source_key": str(incoming_meta.get("source_key") or incoming_meta.get("source") or "UNKNOWN"),
                "value": incoming_value,
                "raw_id": incoming_meta.get("raw_source_record_id"),
                "observed_at": str(incoming_meta.get("observed_at") or ""),
                "evidence_grade": str(incoming_meta.get("evidence_grade") or ""),
                "source_priority": incoming_meta.get("source_priority"),
            }
        )
    return out


def _append_conflict_queue(
    db: Session,
    *,
    registration_id: UUID,
    registration_no: str,
    field_name: str,
    source_run_id: int | None,
    candidates: list[dict[str, Any]],
) -> None:
    row = db.scalar(
        select(ConflictQueue).where(
            ConflictQueue.registration_no == registration_no,
            ConflictQueue.field_name == field_name,
            ConflictQueue.status == "open",
        )
    )
    if row is None:
        db.add(
            ConflictQueue(
                registration_id=registration_id,
                registration_no=registration_no,
                field_name=field_name,
                candidates=candidates,
                status="open",
                source_run_id=source_run_id,
            )
        )
        return
    existing = row.candidates if isinstance(row.candidates, list) else []
    seen = {
        (
            str(item.get("source_key") or ""),
            str(item.get("value") or ""),
            str(item.get("observed_at") or ""),
        )
        for item in existing
        if isinstance(item, dict)
    }
    for item in candidates:
        key = (
            str(item.get("source_key") or ""),
            str(item.get("value") or ""),
            str(item.get("observed_at") or ""),
        )
        if key in seen:
            continue
        existing.append(item)
        seen.add(key)
    row.candidates = existing
    row.updated_at = _utcnow()
    db.add(row)


@dataclass
class RegistrationUpsertResult:
    registration_id: UUID
    registration_no: str
    created: bool
    changed_fields: dict[str, dict[str, Any]]
    raw_source_record_id: UUID | None


@dataclass
class FieldPolicyDecision:
    action: str  # apply | keep | conflict | noop
    reason: str
    value_to_store: str | None
    incoming_meta: dict[str, Any]


def _load_source_policy(db: Session, source_key: str) -> tuple[str, int]:
    key = str(source_key or "").strip().upper()
    if not key:
        return ("C", 10_000)
    # Unit tests may pass a lightweight FakeDB without SQLAlchemy APIs.
    # Fallback to safe defaults in that case; contract validation happens in ingest_runner.
    try:
        defn = db.get(SourceDefinition, key)  # type: ignore[attr-defined]
        cfg = db.scalar(select(SourceConfig).where(SourceConfig.source_key == key))  # type: ignore[attr-defined]
    except Exception:
        return ("C", 10_000)
    grade = _grade((defn.default_evidence_grade if defn is not None else "C"), default="C")
    priority = 10_000
    if cfg is not None and isinstance(cfg.upsert_policy, dict):
        try:
            priority = int(cfg.upsert_policy.get("priority", 10_000))
        except Exception:
            priority = 10_000
    return (grade, priority)


def apply_field_policy(
    db: Session,
    *,
    field_name: str,
    old_value: Any,
    new_value: Any,
    source_key: str,
    observed_at: datetime | None,
    existing_meta: dict[str, Any] | None = None,
    source_run_id: int | None = None,
    raw_source_record_id: UUID | None = None,
    policy_evidence_grade: str | None = None,
    policy_source_priority: int | None = None,
) -> FieldPolicyDecision:
    old_text = _as_text(old_value)
    new_text = _as_text(new_value)
    if new_text is None:
        return FieldPolicyDecision(action="noop", reason="new_value_empty", value_to_store=old_text, incoming_meta={})
    if old_text == new_text:
        return FieldPolicyDecision(action="noop", reason="same_value", value_to_store=old_text, incoming_meta={})

    if policy_evidence_grade is None or policy_source_priority is None:
        resolved_grade, resolved_priority = _load_source_policy(db, source_key)
    else:
        resolved_grade, resolved_priority = (_grade(policy_evidence_grade), int(policy_source_priority))
    evidence_grade = (policy_evidence_grade if policy_evidence_grade is not None else resolved_grade)
    source_priority = (policy_source_priority if policy_source_priority is not None else resolved_priority)
    now = _as_dt(observed_at)
    incoming_meta = {
        "source": str(source_key or "UNKNOWN"),
        "source_key": str(source_key or "UNKNOWN"),
        "source_run_id": (int(source_run_id) if source_run_id is not None else None),
        "evidence_grade": evidence_grade,
        "source_priority": int(source_priority),
        "observed_at": now.isoformat(),
        "raw_source_record_id": (str(raw_source_record_id) if raw_source_record_id else None),
        "field_name": str(field_name or ""),
    }

    unresolved_tie = (
        _same_rank(existing_meta, incoming_meta)
        and _same_observed_at(existing_meta, incoming_meta)
        and old_text is not None
        and new_text is not None
        and old_text != new_text
    )
    if unresolved_tie:
        return FieldPolicyDecision(
            action="conflict",
            reason="same_grade_priority_time_requires_manual",
            value_to_store=old_text,
            incoming_meta=incoming_meta,
        )

    if _should_take(existing_meta, incoming_meta):
        return FieldPolicyDecision(
            action="apply",
            reason="accepted_by_field_policy",
            value_to_store=new_text,
            incoming_meta=incoming_meta,
        )

    return FieldPolicyDecision(
        action="keep",
        reason=_reject_reason(existing_meta, incoming_meta),
        value_to_store=old_text,
        incoming_meta=incoming_meta,
    )


def registration_contract_daily_summary(
    db: Session,
    *,
    target_date: date,
) -> dict[str, Any]:
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return registration_contract_summary(db, start=start, end=end)


def registration_contract_summary(
    db: Session,
    *,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    start_ts = _as_dt(start)
    end_ts = _as_dt(end)

    totals = db.execute(
        text(
            """
            SELECT
                COUNT(1) AS total,
                COUNT(1) FILTER (WHERE change_type = 'new') AS created,
                COUNT(1) FILTER (WHERE change_type = 'update') AS updated,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(changed_fields) = 'object'
                            THEN (SELECT COUNT(1) FROM jsonb_object_keys(changed_fields))
                        ELSE 0
                    END
                ), 0) AS changed_fields_total
            FROM change_log
            WHERE entity_type = 'registration'
              AND changed_at >= :start_ts
              AND changed_at < :end_ts
            """
        ),
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().one()

    by_source = db.execute(
        text(
            """
            SELECT
                COALESCE(after_raw->'_contract_meta'->>'source', 'unknown') AS source,
                COALESCE(after_raw->'_contract_meta'->>'evidence_grade', 'unknown') AS evidence_grade,
                COALESCE((after_raw->'_contract_meta'->>'source_priority')::int, 999999) AS source_priority,
                COUNT(1) AS applied_changes,
                COALESCE(SUM(
                    CASE
                        WHEN jsonb_typeof(changed_fields) = 'object'
                            THEN (SELECT COUNT(1) FROM jsonb_object_keys(changed_fields))
                        ELSE 0
                    END
                ), 0) AS changed_fields_total
            FROM change_log
            WHERE entity_type = 'registration'
              AND changed_at >= :start_ts
              AND changed_at < :end_ts
            GROUP BY 1, 2, 3
            ORDER BY evidence_grade ASC, source_priority ASC, applied_changes DESC
            """
        ),
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().all()

    rejected = db.execute(
        text(
            """
            SELECT
                COALESCE(incoming_meta->>'source', 'unknown') AS source,
                COALESCE(incoming_meta->>'evidence_grade', 'unknown') AS evidence_grade,
                COALESCE((incoming_meta->>'source_priority')::int, 999999) AS source_priority,
                COUNT(1) AS rejected_changes
            FROM registration_conflict_audit
            WHERE resolution = 'REJECTED'
              AND created_at >= :start_ts
              AND created_at < :end_ts
            GROUP BY 1, 2, 3
            ORDER BY evidence_grade ASC, source_priority ASC, rejected_changes DESC
            """
        ),
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().all()

    by_day = db.execute(
        text(
            """
            SELECT
                day::date AS day,
                SUM(applied_changes) AS applied_changes,
                SUM(rejected_changes) AS rejected_changes
            FROM (
                SELECT date_trunc('day', changed_at) AS day, COUNT(1) AS applied_changes, 0::bigint AS rejected_changes
                FROM change_log
                WHERE entity_type = 'registration'
                  AND changed_at >= :start_ts
                  AND changed_at < :end_ts
                GROUP BY 1
                UNION ALL
                SELECT date_trunc('day', created_at) AS day, 0::bigint AS applied_changes, COUNT(1) AS rejected_changes
                FROM registration_conflict_audit
                WHERE created_at >= :start_ts
                  AND created_at < :end_ts
                GROUP BY 1
            ) t
            GROUP BY 1
            ORDER BY 1 ASC
            """
        ),
        {"start_ts": start_ts, "end_ts": end_ts},
    ).mappings().all()

    rejected_total = int(sum(int(r.get("rejected_changes") or 0) for r in rejected))

    return {
        "window_start": start_ts.isoformat(),
        "window_end": end_ts.isoformat(),
        "totals": {
            "total": int(totals.get("total") or 0),
            "created": int(totals.get("created") or 0),
            "updated": int(totals.get("updated") or 0),
            "changed_fields_total": int(totals.get("changed_fields_total") or 0),
            "rejected_total": rejected_total,
        },
        "by_source": [
            {
                "source": str(r.get("source") or "unknown"),
                "evidence_grade": str(r.get("evidence_grade") or "unknown"),
                "source_priority": int(r.get("source_priority") or 999999),
                "applied_changes": int(r.get("applied_changes") or 0),
                "changed_fields_total": int(r.get("changed_fields_total") or 0),
            }
            for r in by_source
        ],
        "rejected_by_source": [
            {
                "source": str(r.get("source") or "unknown"),
                "evidence_grade": str(r.get("evidence_grade") or "unknown"),
                "source_priority": int(r.get("source_priority") or 999999),
                "rejected_changes": int(r.get("rejected_changes") or 0),
            }
            for r in rejected
        ],
        "by_day": [
            {
                "date": str(r.get("day")),
                "applied_changes": int(r.get("applied_changes") or 0),
                "rejected_changes": int(r.get("rejected_changes") or 0),
            }
            for r in by_day
        ],
    }


def upsert_registration_with_contract(
    db: Session,
    *,
    registration_no: str,
    incoming_fields: dict[str, Any] | None,
    source: str,
    source_run_id: int | None,
    evidence_grade: str,
    source_priority: int,
    observed_at: datetime | None = None,
    raw_source_record_id: UUID | None = None,
    raw_payload: dict[str, Any] | None = None,
    write_change_log: bool = True,
) -> RegistrationUpsertResult:
    """Upsert registration with deterministic conflict resolution.

    Decision order:
    1) evidence_grade (A > B > C > D)
    2) source_priority (smaller number wins)
    3) observed_at (newer wins)
    """
    reg_no = normalize_registration_no(registration_no)
    if not reg_no:
        raise ValueError("registration_no is required")

    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    fields = dict(incoming_fields or {})
    now = observed_at if observed_at is not None else _utcnow()
    meta_base = {
        "source": str(source or "UNKNOWN"),
        "source_key": str(source or "UNKNOWN"),
        "source_run_id": (int(source_run_id) if source_run_id is not None else None),
        "evidence_grade": _grade(evidence_grade),
        "source_priority": int(source_priority),
        "observed_at": _as_dt(now).isoformat(),
        "raw_source_record_id": (str(raw_source_record_id) if raw_source_record_id else None),
    }

    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no))
    created = False
    if reg is None:
        reg = Registration(registration_no=reg_no, raw_json={})
        db.add(reg)
        db.flush()
        created = True

    before = {
        "registration_no": reg.registration_no,
        "filing_no": _as_text(reg.filing_no),
        "approval_date": _as_text(reg.approval_date),
        "expiry_date": _as_text(reg.expiry_date),
        "status": _as_text(reg.status),
    }

    reg_raw = copy.deepcopy(reg.raw_json) if isinstance(reg.raw_json, dict) else {}
    field_meta = copy.deepcopy(reg.field_meta) if isinstance(reg.field_meta, dict) else {}
    prov = reg_raw.get("_contract_provenance")
    if not isinstance(prov, dict):
        prov = {}
    changed: dict[str, dict[str, Any]] = {}

    for k in _REG_FIELDS:
        if k not in fields:
            continue
        incoming = fields.get(k)
        old_text = before.get(k)
        existing_meta = prov.get(k) if isinstance(prov.get(k), dict) else None
        decision = apply_field_policy(
            db,
            field_name=str(k),
            old_value=old_text,
            new_value=incoming,
            source_key=str(source or "UNKNOWN"),
            observed_at=now,
            existing_meta=existing_meta,
            source_run_id=source_run_id,
            raw_source_record_id=raw_source_record_id,
            policy_evidence_grade=_grade(evidence_grade),
            policy_source_priority=int(source_priority),
        )
        incoming_text = _as_text(incoming)
        if decision.action == "noop":
            continue
        if decision.action == "conflict":
            reason = "same_grade_priority_time_requires_manual"
            field_meta[k] = _field_meta_entry(
                source_key=str(source or "UNKNOWN"),
                incoming_meta=decision.incoming_meta,
                decision=reason,
            )
            candidates = _queue_conflict_candidates(
                old_value=old_text,
                incoming_value=incoming_text,
                existing_meta=existing_meta,
                incoming_meta=decision.incoming_meta,
            )
            _append_conflict_queue(
                db,
                registration_id=reg.id,
                registration_no=reg.registration_no,
                field_name=str(k),
                source_run_id=source_run_id,
                candidates=candidates,
            )
            db.add(
                RegistrationConflictAudit(
                    registration_id=reg.id,
                    registration_no=reg.registration_no,
                    field_name=str(k),
                    old_value=old_text,
                    incoming_value=incoming_text,
                    final_value=old_text,
                    resolution="REJECTED",
                    reason=reason,
                    existing_meta=(existing_meta if isinstance(existing_meta, dict) else None),
                    incoming_meta=decision.incoming_meta,
                    source_run_id=source_run_id,
                    observed_at=_as_dt(now),
                )
            )
            continue
        if decision.action == "keep":
            field_meta[k] = _field_meta_entry(
                source_key=str(source or "UNKNOWN"),
                incoming_meta=decision.incoming_meta,
                decision=str(decision.reason or "keep"),
            )
            db.add(
                RegistrationConflictAudit(
                    registration_id=reg.id,
                    registration_no=reg.registration_no,
                    field_name=str(k),
                    old_value=old_text,
                    incoming_value=incoming_text,
                    final_value=old_text,
                    resolution="REJECTED",
                    reason=decision.reason,
                    existing_meta=(existing_meta if isinstance(existing_meta, dict) else None),
                    incoming_meta=decision.incoming_meta,
                    source_run_id=source_run_id,
                    observed_at=_as_dt(now),
                )
            )
            continue
        if k in ("approval_date", "expiry_date"):
            parsed = _as_date(incoming)
            if parsed is None:
                continue
            setattr(reg, k, parsed)
        else:
            setattr(reg, k, incoming_text)
        changed[k] = {"old": old_text, "new": incoming_text}
        prov[k] = dict(decision.incoming_meta)
        field_meta[k] = _field_meta_entry(
            source_key=str(source or "UNKNOWN"),
            incoming_meta=decision.incoming_meta,
            decision=str(decision.reason or "apply"),
        )
        db.add(
            RegistrationConflictAudit(
                registration_id=reg.id,
                registration_no=reg.registration_no,
                field_name=str(k),
                old_value=old_text,
                incoming_value=incoming_text,
                final_value=incoming_text,
                resolution="APPLIED",
                reason=decision.reason,
                existing_meta=(existing_meta if isinstance(existing_meta, dict) else None),
                incoming_meta=decision.incoming_meta,
                source_run_id=source_run_id,
                observed_at=_as_dt(now),
            )
        )

    reg_raw["_contract_provenance"] = prov
    if payload:
        reg_raw["_latest_payload"] = _json_payload(payload)
    reg.raw_json = reg_raw
    reg.field_meta = field_meta
    db.add(reg)

    if write_change_log and (created or changed):
        after = {
            "registration_no": reg.registration_no,
            "filing_no": _as_text(reg.filing_no),
            "approval_date": _as_text(reg.approval_date),
            "expiry_date": _as_text(reg.expiry_date),
            "status": _as_text(reg.status),
        }
        db.add(
            ChangeLog(
                product_id=None,
                entity_type="registration",
                entity_id=reg.id,
                change_type=("new" if created else "update"),
                changed_fields=(changed or {"registration_no": {"old": None, "new": reg.registration_no}}),
                before_json=(None if created else before),
                after_json=after,
                before_raw=(None if created else before),
                after_raw={
                    "_contract_meta": meta_base,
                    "payload": (_json_payload(payload) if payload else None),
                },
                source_run_id=source_run_id,
            )
        )

    return RegistrationUpsertResult(
        registration_id=reg.id,
        registration_no=reg.registration_no,
        created=created,
        changed_fields=changed,
        raw_source_record_id=raw_source_record_id,
    )


@dataclass
class UdiContractWriteResult:
    raw_record_id: UUID | None
    registration_no_norm: str | None
    di: str | None
    map_written: bool
    pending_written: bool
    parse_status: str
    error: str | None = None


def write_udi_contract_record(
    db: Session,
    *,
    row: dict[str, Any],
    source: str,
    source_run_id: int | None,
    source_url: str | None = None,
    evidence_grade: str | None = None,
    confidence: float = 0.80,
) -> UdiContractWriteResult:
    """Best-effort Source Contract write for one UDI row.

    Stages (non-blocking in callers):
    - Fetch: persist raw payload into raw_source_records.
    - Parse/Normalize: derive di + normalized registration_no.
    - Upsert split:
      - registration_no resolved -> product_udi_map
      - registration_no missing -> udi_di_master + pending_udi_links
    """
    di = _pick_text(row, "udi_di", "di", "zxxsdycpbs", "UDI_DI", "primary_di")
    raw_reg_no = (
        _pick_text(row, "registry_no", "reg_no", "registration_no", "zczbhhzbapzbh")
    )
    reg_norm = normalize_registration_no(raw_reg_no)
    parsed_reg = parse_registration_no(reg_norm) if reg_norm else None
    has_cert = _parse_bool_zh(_pick_text(row, "sfyzcbayz", "has_cert"))
    packaging_json = _parse_packaging_json(row)
    storage_json = _parse_storage_json(row)

    parse_error: str | None = None
    gate_reason_code: str | None = None
    if not di:
        parse_error = "missing di"
    elif not reg_norm:
        gate_reason_code = "REGNO_MISSING"
    elif parsed_reg is not None and not parsed_reg.parse_ok:
        gate_reason_code = "REGNO_PARSE_FAILED"

    payload_hash = _payload_hash(row)
    now = _utcnow()
    parse_status = _parse_status_for((reg_norm if gate_reason_code is None else None), di, parse_error)

    raw_stmt = insert(RawSourceRecord).values(
        source=str(source or "UNKNOWN"),
        source_run_id=source_run_id,
        source_url=(str(source_url).strip() if source_url else None),
        payload_hash=payload_hash,
        evidence_grade=_grade(evidence_grade),
        observed_at=now,
        payload=_json_payload(row),
        parse_status=parse_status,
        parse_error=parse_error,
    )
    raw_stmt = raw_stmt.on_conflict_do_update(
        index_elements=[RawSourceRecord.source_run_id, RawSourceRecord.payload_hash],
        set_={
            "source_url": raw_stmt.excluded.source_url,
            "evidence_grade": raw_stmt.excluded.evidence_grade,
            "observed_at": raw_stmt.excluded.observed_at,
            "payload": raw_stmt.excluded.payload,
            "parse_status": raw_stmt.excluded.parse_status,
            "parse_error": raw_stmt.excluded.parse_error,
            "updated_at": text("NOW()"),
        },
    ).returning(RawSourceRecord.id)
    raw_id = db.execute(raw_stmt).scalar_one()

    if parse_error:
        return UdiContractWriteResult(
            raw_record_id=raw_id,
            registration_no_norm=reg_norm,
            di=di,
            map_written=False,
            pending_written=False,
            parse_status=parse_status,
            error=parse_error,
        )

    if di:
        master_stmt = insert(UdiDiMaster).values(
            di=di,
            payload_hash=payload_hash,
            source=str(source or "UNKNOWN"),
            has_cert=has_cert,
            registration_no_norm=(reg_norm or None),
            packaging_json=(_json_payload(packaging_json) if packaging_json else None),
            storage_json=(_json_payload(storage_json) if storage_json else None),
            first_seen_at=now,
            last_seen_at=now,
            raw_source_record_id=raw_id,
        )
        master_stmt = master_stmt.on_conflict_do_update(
            index_elements=[UdiDiMaster.di],
            set_={
                "payload_hash": master_stmt.excluded.payload_hash,
                "source": master_stmt.excluded.source,
                "has_cert": master_stmt.excluded.has_cert,
                "registration_no_norm": func.coalesce(master_stmt.excluded.registration_no_norm, UdiDiMaster.registration_no_norm),
                "packaging_json": func.coalesce(master_stmt.excluded.packaging_json, UdiDiMaster.packaging_json),
                "storage_json": func.coalesce(master_stmt.excluded.storage_json, UdiDiMaster.storage_json),
                "last_seen_at": master_stmt.excluded.last_seen_at,
                "raw_source_record_id": master_stmt.excluded.raw_source_record_id,
                "updated_at": text("NOW()"),
            },
        )
        db.execute(master_stmt)

    if reg_norm and gate_reason_code is None:
        def _ensure_anchor_product(registration_id: UUID, registration_no: str, payload: dict[str, Any]) -> None:
            # Keep one lightweight "anchor product" so search/workbench can reach this registration.
            product = db.scalar(
                select(Product)
                .where(Product.registration_id == registration_id)
                .order_by(Product.updated_at.desc(), Product.created_at.desc())
                .limit(1)
            )
            if product is None:
                product = db.scalar(select(Product).where(Product.reg_no == registration_no).order_by(Product.updated_at.desc()).limit(1))
            if product is None:
                product = db.scalar(select(Product).where(Product.udi_di == f"reg:{registration_no}").limit(1))

            name = (
                _pick_text(payload, "product_name", "name", "catalog_item_std", "catalog_item_raw")
                or registration_no
            )[:500]
            status = (_pick_text(payload, "status", "registration_status") or "UNKNOWN")[:20]
            ivd_category = _pick_text(payload, "ivd_category", "category", "product_type", "cplb")

            if product is None:
                product = Product(
                    udi_di=f"reg:{registration_no}",
                    reg_no=registration_no,
                    name=name,
                    status=status,
                    approved_date=None,
                    expiry_date=None,
                    class_name=None,
                    model=None,
                    specification=None,
                    category=None,
                    is_ivd=True,
                    ivd_category=ivd_category,
                    ivd_subtypes=None,
                    ivd_reason=None,
                    ivd_version=1,
                    ivd_source="UDI_CONTRACT",
                    ivd_confidence=0.40,
                    company_id=None,
                    registration_id=registration_id,
                    raw_json={"_stub": {"source_hint": "UDI", "verified_by_nmpa": False, "evidence_level": "LOW"}},
                    raw={},
                )
                db.add(product)
                return

            changed = False
            if not getattr(product, "registration_id", None):
                product.registration_id = registration_id
                changed = True
            if not str(getattr(product, "reg_no", "") or "").strip():
                product.reg_no = registration_no
                changed = True
            if not str(getattr(product, "name", "") or "").strip():
                product.name = name
                changed = True
            if not str(getattr(product, "status", "") or "").strip():
                product.status = status
                changed = True
            if getattr(product, "is_ivd", None) is None:
                product.is_ivd = True
                changed = True
            if changed:
                db.add(product)

        reg_res = upsert_registration_with_contract(
            db,
            registration_no=reg_norm,
            incoming_fields={},
            source=str(source or "UNKNOWN"),
            source_run_id=source_run_id,
            evidence_grade=_grade(evidence_grade),
            source_priority=100,
            observed_at=now,
            raw_source_record_id=raw_id,
            raw_payload=row,
            write_change_log=True,
        )
        reg_norm = reg_res.registration_no
        # Keep DI linked to a single canonical registration_no in map.
        db.execute(
            text("DELETE FROM product_udi_map WHERE di = :di AND registration_no <> :registration_no"),
            {"di": di, "registration_no": reg_norm},
        )
        map_stmt = insert(ProductUdiMap).values(
            registration_no=reg_norm,
            di=di,
            source=str(source or "UNKNOWN"),
            match_type="direct",
            confidence=0.95,
            raw_source_record_id=raw_id,
        )
        map_stmt = map_stmt.on_conflict_do_update(
            index_elements=[ProductUdiMap.registration_no, ProductUdiMap.di],
            set_={
                "source": map_stmt.excluded.source,
                "match_type": map_stmt.excluded.match_type,
                "confidence": map_stmt.excluded.confidence,
                "raw_source_record_id": map_stmt.excluded.raw_source_record_id,
                "updated_at": text("NOW()"),
            },
        )
        db.execute(map_stmt)
        _ensure_anchor_product(reg_res.registration_id, reg_norm, row)
        # Resolve existing pending item if direct mapping succeeded.
        db.execute(
            text(
                """
                UPDATE pending_udi_links
                SET status = 'RESOLVED',
                    resolved_at = NOW(),
                    resolved_by = :resolved_by,
                    updated_at = NOW()
                WHERE di = :di AND status IN ('PENDING','RETRYING')
                """
            ),
            {"di": di, "resolved_by": str(source or "UNKNOWN")},
        )
        return UdiContractWriteResult(
            raw_record_id=raw_id,
            registration_no_norm=reg_norm,
            di=di,
            map_written=True,
            pending_written=False,
            parse_status=parse_status,
        )

    candidate_company_name = _pick_text(
        row,
        "manufacturer",
        "company_name",
        "win_company_text",
        "producer_name",
    )
    candidate_product_name = _pick_text(
        row,
        "product_name",
        "name",
        "catalog_item_std",
        "catalog_item_raw",
    )
    reason_code = gate_reason_code or ("REGNO_MISSING" if raw_reg_no is None else "REGISTRATION_NO_NOT_FOUND")
    reason_text = (
        "registration_no missing after normalize"
        if reason_code == "REGNO_MISSING"
        else ("registration_no semantic parse failed" if reason_code == "REGNO_PARSE_FAILED" else "registration_no_not_found")
    )

    pending_stmt = insert(PendingUdiLink).values(
        di=di,
        reason=reason_text,
        reason_code=reason_code,
        raw_id=raw_id,
        retry_count=0,
        next_retry_at=None,
        status="PENDING",
        candidate_company_name=candidate_company_name,
        candidate_product_name=candidate_product_name,
        raw_source_record_id=raw_id,
    )
    pending_stmt = pending_stmt.on_conflict_do_update(
        index_elements=[PendingUdiLink.di],
        index_where=text("status IN ('PENDING','RETRYING')"),
        set_={
            "reason": pending_stmt.excluded.reason,
            "reason_code": pending_stmt.excluded.reason_code,
            "raw_id": pending_stmt.excluded.raw_id,
            "raw_source_record_id": pending_stmt.excluded.raw_source_record_id,
            "candidate_company_name": pending_stmt.excluded.candidate_company_name,
            "candidate_product_name": pending_stmt.excluded.candidate_product_name,
            "updated_at": text("NOW()"),
        },
    )
    db.execute(pending_stmt)

    return UdiContractWriteResult(
        raw_record_id=raw_id,
        registration_no_norm=reg_norm,
        di=di,
        map_written=False,
        pending_written=True,
        parse_status=parse_status,
    )
