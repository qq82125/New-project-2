from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChangeLog, FieldDiff, NmpaSnapshot, Registration, RegistrationEvent


EVENT_INITIAL = "INITIAL"
EVENT_CHANGE = "CHANGE"
EVENT_RENEWAL = "RENEWAL"
EVENT_CANCEL = "CANCEL"
EVENT_UNKNOWN = "UNKNOWN"


SSOT_DIFF_FIELDS: tuple[str, ...] = (
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


def _as_date(d: Any) -> date | None:
    if isinstance(d, date):
        return d
    if isinstance(d, str) and len(d) >= 10:
        try:
            return date.fromisoformat(d[:10])
        except Exception:
            return None
    return None


def _status_normalize(s: str | None) -> str:
    t = (s or "").strip().lower()
    if not t:
        return ""
    if t in {"cancel", "cancelled", "注销"}:
        return "cancelled"
    return t


def _detect_event_type(*, diffs: list[FieldDiff], reg: Registration | None, is_first_snapshot: bool) -> str:
    if is_first_snapshot:
        return EVENT_INITIAL

    old_status = None
    new_status = None
    old_exp = None
    new_exp = None
    for d in diffs:
        if d.field_name == "status":
            old_status = _status_normalize(d.old_value)
            new_status = _status_normalize(d.new_value)
        if d.field_name == "expiry_date":
            old_exp = _as_date(d.old_value)
            new_exp = _as_date(d.new_value)

    # Cancellation dominates.
    if new_status == "cancelled":
        return EVENT_CANCEL
    if reg is not None and _status_normalize(getattr(reg, "status", None)) == "cancelled":
        return EVENT_CANCEL

    # Renewal heuristic: expiry_date increased or explicit diff exists.
    if old_exp and new_exp and new_exp > old_exp:
        return EVENT_RENEWAL

    # Otherwise, if there are any diffs, it's a change.
    if diffs:
        return EVENT_CHANGE
    return EVENT_UNKNOWN


def _build_summary(event_type: str, diffs: list[FieldDiff]) -> str:
    # Keep it short and stable.
    fields = [d.field_name for d in diffs if d.field_name]
    fields = [f for f in fields if f in SSOT_DIFF_FIELDS]
    fields = list(dict.fromkeys(fields))
    if event_type == EVENT_INITIAL:
        return "initial snapshot"
    if event_type == EVENT_CANCEL:
        return "status cancelled"
    if event_type == EVENT_RENEWAL:
        return "expiry_date extended"
    if fields:
        return "changed: " + ", ".join(fields[:8])
    return event_type.lower()


@dataclass
class EventsRunResult:
    ok: bool
    dry_run: bool
    date: str | None
    since: str | None
    scanned_snapshots: int
    groups_with_diffs: int
    inserted_events: int
    inserted_change_logs: int
    skipped_existing: int
    samples: list[dict[str, Any]]
    error: str | None = None


def generate_registration_events(
    db: Session,
    *,
    target_date: date | None = None,
    since: date | None = None,
    dry_run: bool = True,
) -> EventsRunResult:
    if target_date and since:
        return EventsRunResult(
            ok=False,
            dry_run=dry_run,
            date=str(target_date),
            since=str(since),
            scanned_snapshots=0,
            groups_with_diffs=0,
            inserted_events=0,
            inserted_change_logs=0,
            skipped_existing=0,
            samples=[],
            error="only one of --date/--since is allowed",
        )

    q = select(NmpaSnapshot).order_by(NmpaSnapshot.snapshot_date.asc(), NmpaSnapshot.created_at.asc())
    if target_date:
        q = q.where(NmpaSnapshot.snapshot_date == target_date)
    if since:
        q = q.where(NmpaSnapshot.snapshot_date >= since)

    snapshots = db.scalars(q).all()
    scanned = len(snapshots)

    inserted_events = 0
    inserted_change_logs = 0
    skipped_existing = 0
    groups_with_diffs = 0
    samples: list[dict[str, Any]] = []

    for snap in snapshots:
        # Load diffs for this snapshot, restricted to SSOT fields.
        diffs = db.scalars(
            select(FieldDiff).where(
                FieldDiff.snapshot_id == snap.id,
                FieldDiff.field_name.in_(SSOT_DIFF_FIELDS),
            )
        ).all()
        if diffs:
            groups_with_diffs += 1

        reg = db.get(Registration, snap.registration_id)

        # Determine if this is the first snapshot for this registration.
        is_first_snapshot = False
        try:
            prev_id = db.scalar(
                select(NmpaSnapshot.id)
                .where(
                    NmpaSnapshot.registration_id == snap.registration_id,
                    NmpaSnapshot.snapshot_date < snap.snapshot_date,
                )
                .order_by(NmpaSnapshot.snapshot_date.desc())
                .limit(1)
            )
            is_first_snapshot = prev_id is None
        except Exception:
            is_first_snapshot = False

        event_type = _detect_event_type(diffs=diffs, reg=reg, is_first_snapshot=is_first_snapshot)
        event_date = snap.snapshot_date
        summary = _build_summary(event_type, diffs)

        if len(samples) < 20:
            samples.append(
                {
                    "registration_id": str(snap.registration_id),
                    "registration_no": (getattr(reg, "registration_no", None) if reg else None),
                    "source_run_id": (int(snap.source_run_id) if snap.source_run_id is not None else None),
                    "snapshot_id": str(snap.id),
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                    "summary": summary,
                    "diff_fields": [d.field_name for d in diffs],
                }
            )

        if dry_run:
            continue

        # Idempotent insert per (registration_id, source_run_id, event_type).
        stmt = insert(RegistrationEvent).values(
            registration_id=snap.registration_id,
            event_type=event_type,
            event_date=event_date,
            summary=summary,
            source_run_id=snap.source_run_id,
            snapshot_id=snap.id,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[RegistrationEvent.registration_id, RegistrationEvent.source_run_id, RegistrationEvent.event_type]
        ).returning(RegistrationEvent.id)

        event_id = db.execute(stmt).scalar_one_or_none()
        if event_id is None:
            skipped_existing += 1
            continue
        inserted_events += 1

        # Reuse change_log chain for subscriptions/digest.
        changed_fields = {
            "event_type": {"old": None, "new": event_type},
            "event_date": {"old": None, "new": event_date.isoformat()},
        }
        if summary:
            changed_fields["summary"] = {"old": None, "new": summary}

        db.add(
            ChangeLog(
                product_id=None,
                entity_type="registration",
                entity_id=snap.registration_id,
                change_type="update",
                changed_fields=changed_fields,
                before_json=None,
                after_json={
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "event_date": event_date.isoformat(),
                    "summary": summary,
                    "snapshot_id": str(snap.id),
                    "source_run_id": (int(snap.source_run_id) if snap.source_run_id is not None else None),
                },
                after_raw={"kind": "registration_event"},
                source_run_id=snap.source_run_id,
            )
        )
        inserted_change_logs += 1
        db.commit()

    return EventsRunResult(
        ok=True,
        dry_run=bool(dry_run),
        date=(target_date.isoformat() if target_date else None),
        since=(since.isoformat() if since else None),
        scanned_snapshots=scanned,
        groups_with_diffs=groups_with_diffs,
        inserted_events=inserted_events,
        inserted_change_logs=inserted_change_logs,
        skipped_existing=skipped_existing,
        samples=samples,
    )
