from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import FieldDiff, NmpaSnapshot, RawDocument, Registration, RegistrationEvent


EVENT_APPROVE = "approve"
EVENT_RENEW = "renew"
EVENT_CHANGE = "change"
EVENT_CANCEL = "cancel"
EVENT_EXPIRE = "expire"


CANCEL_KEYWORDS = ("注销", "撤销", "失效", "停止", "取消", "不予注册")

# "change" whitelist (field_diffs.field_name)
CHANGE_FIELDS = {
    "product_name",
    "model",
    "specification",
    "intended_use",
    "class",
    "address",
    "registrant",
    "composition",
}


def _utc_dt_for_day(d: date) -> datetime:
    return datetime.combine(d, time.min).replace(tzinfo=timezone.utc)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    t = str(s).strip()
    if not t:
        return None
    # Accept common formats; field_diffs often stores ISO-like strings.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(t[:10], fmt).date()
        except Exception:
            continue
    try:
        return date.fromisoformat(t[:10])
    except Exception:
        return None


def _looks_cancelled(s: str | None) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    return any(k in t for k in CANCEL_KEYWORDS)


def _dedup_hash(
    *,
    registration_id: UUID,
    event_type: str,
    event_date: date,
    effective_to: date | None,
) -> str:
    base = f"{registration_id}|{event_type}|{event_date.isoformat()}|{effective_to.isoformat() if effective_to else ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


@dataclass
class DeriveEventsResult:
    ok: bool
    dry_run: bool
    since: str
    candidates: int
    by_type: dict[str, int]
    deduped: int
    inserted: int
    seq_recomputed_regs: int
    error: str | None = None
    samples: list[dict[str, Any]] | None = None


def derive_registration_events_v1(
    db: Session,
    *,
    since: date,
    dry_run: bool = True,
) -> DeriveEventsResult:
    """Derive business events into registration_events from field_diffs and registrations lifecycle.

    V1 rules:
    - approve: registration created (no approve event exists yet)
    - renew: expiry_date increased (new > old)
    - cancel: status becomes cancelled keywords
    - change: other whitelisted fields changed
    - expire: expiry_date < today and no expire event yet
    """
    samples: list[dict[str, Any]] = []
    by_type: dict[str, int] = {EVENT_APPROVE: 0, EVENT_RENEW: 0, EVENT_CHANGE: 0, EVENT_CANCEL: 0, EVENT_EXPIRE: 0}

    # 1) Approve events: registrations created since window and without approve event.
    approve_regs = db.scalars(
        select(Registration).where(func.date(Registration.created_at) >= since).order_by(Registration.created_at.asc())
    ).all()

    approve_candidates: list[dict[str, Any]] = []
    if approve_regs:
        existing_approve = set(
            db.execute(
                text(
                    """
                    SELECT registration_id
                    FROM registration_events
                    WHERE event_type = :t
                      AND registration_id = ANY(:ids)
                    """
                ),
                {"t": EVENT_APPROVE, "ids": [r.id for r in approve_regs]},
            ).scalars().all()
        )
        for r in approve_regs:
            if r.id in existing_approve:
                continue
            event_date = (r.approval_date or r.created_at.date())
            approve_candidates.append(
                {
                    "registration_id": r.id,
                    "event_type": EVENT_APPROVE,
                    "event_date": event_date,
                    "effective_from": r.approval_date,
                    "effective_to": r.expiry_date,
                    "observed_at": r.created_at,
                    "source_run_id": None,
                    "raw_document_id": None,
                    "snapshot_id": None,
                    "summary": "approve (registration created)",
                    "notes": None,
                    "diff_json": None,
                }
            )

    # 2) Diff-driven events (renew/cancel/change)
    snap_q = select(NmpaSnapshot).where(NmpaSnapshot.snapshot_date >= since).order_by(
        NmpaSnapshot.snapshot_date.asc(), NmpaSnapshot.created_at.asc()
    )
    snaps = db.scalars(snap_q).all()

    # Preload diffs for all snapshots in window, and group them by snapshot_id.
    diff_rows = []
    if snaps:
        snap_ids = [s.id for s in snaps]
        diff_rows = db.scalars(
            select(FieldDiff).where(
                FieldDiff.snapshot_id.in_(snap_ids),
            )
        ).all()

    diffs_by_snapshot: dict[UUID, list[FieldDiff]] = {}
    for d in diff_rows:
        diffs_by_snapshot.setdefault(d.snapshot_id, []).append(d)

    diff_candidates: list[dict[str, Any]] = []
    for snap in snaps:
        diffs = diffs_by_snapshot.get(snap.id, [])
        if not diffs:
            continue

        # Determine event type with dominance: cancel > renew > change
        is_cancel = any(d.field_name == "status" and _looks_cancelled(d.new_value) for d in diffs)

        # Renew heuristic: expiry_date increased
        renew_old = None
        renew_new = None
        for d in diffs:
            if d.field_name == "expiry_date":
                renew_old = _parse_date(d.old_value)
                renew_new = _parse_date(d.new_value)
        is_renew = bool(renew_old and renew_new and renew_new > renew_old)

        is_change = any((d.field_name in CHANGE_FIELDS) for d in diffs)

        if is_cancel:
            event_type = EVENT_CANCEL
        elif is_renew:
            event_type = EVENT_RENEW
        elif is_change:
            event_type = EVENT_CHANGE
        else:
            # Ignore diffs outside whitelist for V1 (keeps noise low).
            continue

        # Keep event_date aligned to the snapshot logical date.
        event_date = snap.snapshot_date
        observed_at = _utc_dt_for_day(snap.snapshot_date)
        effective_from = None
        effective_to = None
        if event_type == EVENT_RENEW:
            effective_from = renew_old
            effective_to = renew_new
        elif event_type == EVENT_CANCEL:
            effective_from = snap.snapshot_date
        else:
            effective_from = snap.snapshot_date

        diff_json = {
            "snapshot_id": str(snap.id),
            "snapshot_date": snap.snapshot_date.isoformat(),
            "diffs": [
                {"field_name": d.field_name, "old_value": d.old_value, "new_value": d.new_value}
                for d in diffs
                if d.field_name
            ],
        }
        summary = {
            EVENT_CANCEL: "cancelled (status)",
            EVENT_RENEW: "renew (expiry_date extended)",
            EVENT_CHANGE: "change (field diffs)",
        }.get(event_type, event_type)

        diff_candidates.append(
            {
                "registration_id": snap.registration_id,
                "event_type": event_type,
                "event_date": event_date,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "observed_at": observed_at,
                "source_run_id": (int(snap.source_run_id) if snap.source_run_id is not None else None),
                "raw_document_id": (snap.raw_document_id if snap.raw_document_id is not None else None),
                "snapshot_id": snap.id,
                "summary": summary,
                "notes": None,
                "diff_json": diff_json,
            }
        )

    # 3) Expire events (derived from registrations current facts)
    today = datetime.now(timezone.utc).date()
    expire_regs = db.scalars(
        select(Registration).where(Registration.expiry_date.isnot(None), Registration.expiry_date < today)
    ).all()
    expire_candidates: list[dict[str, Any]] = []
    if expire_regs:
        existing_expire = set(
            db.execute(
                text(
                    """
                    SELECT registration_id
                    FROM registration_events
                    WHERE event_type = :t
                      AND registration_id = ANY(:ids)
                    """
                ),
                {"t": EVENT_EXPIRE, "ids": [r.id for r in expire_regs]},
            ).scalars().all()
        )
        for r in expire_regs:
            if r.id in existing_expire:
                continue
            exp = r.expiry_date
            if exp is None:
                continue
            expire_candidates.append(
                {
                    "registration_id": r.id,
                    "event_type": EVENT_EXPIRE,
                    "event_date": exp,
                    "effective_from": None,
                    "effective_to": exp,
                    "observed_at": _utc_dt_for_day(exp),
                    "source_run_id": None,
                    "raw_document_id": None,
                    "snapshot_id": None,
                    "summary": "expire (expiry_date passed)",
                    "notes": None,
                    "diff_json": None,
                }
            )

    candidates = approve_candidates + diff_candidates + expire_candidates
    for c in candidates:
        by_type[str(c["event_type"])] = int(by_type.get(str(c["event_type"]), 0) or 0) + 1

    if len(candidates) == 0:
        return DeriveEventsResult(
            ok=True,
            dry_run=bool(dry_run),
            since=since.isoformat(),
            candidates=0,
            by_type=by_type,
            deduped=0,
            inserted=0,
            seq_recomputed_regs=0,
            samples=[],
        )

    # 4) Dedup: same day same type same effective_to => keep one.
    existing_keys: set[str] = set()
    reg_ids = sorted({c["registration_id"] for c in candidates})
    if reg_ids:
        rows = db.execute(
            text(
                """
                SELECT registration_id, event_type, event_date, effective_to
                FROM registration_events
                WHERE registration_id = ANY(:ids)
                  AND event_type IN ('approve','renew','change','cancel','expire')
                """
            ),
            {"ids": reg_ids},
        ).mappings().all()
        for r in rows:
            existing_keys.add(
                _dedup_hash(
                    registration_id=r["registration_id"],
                    event_type=str(r["event_type"] or ""),
                    event_date=r["event_date"],
                    effective_to=r["effective_to"],
                )
            )

    deduped = 0
    filtered: list[dict[str, Any]] = []
    seen_new: set[str] = set()
    for c in candidates:
        key = _dedup_hash(
            registration_id=c["registration_id"],
            event_type=str(c["event_type"]),
            event_date=c["event_date"],
            effective_to=c.get("effective_to"),
        )
        if key in existing_keys or key in seen_new:
            deduped += 1
            continue
        seen_new.add(key)
        filtered.append(c)

    if len(samples) < 20:
        for c in filtered[:20]:
            samples.append(
                {
                    "registration_id": str(c["registration_id"]),
                    "event_type": str(c["event_type"]),
                    "event_date": c["event_date"].isoformat(),
                    "effective_to": (c.get("effective_to").isoformat() if c.get("effective_to") else None),
                    "source_run_id": c.get("source_run_id"),
                }
            )

    if dry_run:
        return DeriveEventsResult(
            ok=True,
            dry_run=True,
            since=since.isoformat(),
            candidates=len(candidates),
            by_type=by_type,
            deduped=deduped,
            inserted=0,
            seq_recomputed_regs=len(reg_ids),
            samples=samples,
        )

    inserted = 0
    touched_regs: set[UUID] = set()
    for c in filtered:
        touched_regs.add(c["registration_id"])
        stmt = insert(RegistrationEvent).values(
            registration_id=c["registration_id"],
            event_type=str(c["event_type"]),
            event_date=c["event_date"],
            event_seq=None,
            effective_from=c.get("effective_from"),
            effective_to=c.get("effective_to"),
            observed_at=c.get("observed_at") or datetime.now(timezone.utc),
            summary=c.get("summary"),
            notes=c.get("notes"),
            source_run_id=c.get("source_run_id"),
            raw_document_id=c.get("raw_document_id"),
            diff_json=c.get("diff_json"),
            snapshot_id=c.get("snapshot_id"),
        ).on_conflict_do_nothing(
            index_elements=[RegistrationEvent.registration_id, RegistrationEvent.source_run_id, RegistrationEvent.event_type]
        )
        res = db.execute(stmt)
        # rowcount is reliable for INSERT .. ON CONFLICT DO NOTHING
        try:
            inserted += int(res.rowcount or 0)
        except Exception:
            pass

    # Assign event_seq deterministically for touched registrations.
    if touched_regs:
        db.execute(
            text(
                """
                WITH ranked AS (
                  SELECT
                    id,
                    registration_id,
                    ROW_NUMBER() OVER (
                      PARTITION BY registration_id
                      ORDER BY observed_at ASC NULLS LAST, event_date ASC, created_at ASC, id ASC
                    )::int AS rn
                  FROM registration_events
                  WHERE registration_id = ANY(:ids)
                )
                UPDATE registration_events e
                SET event_seq = ranked.rn
                FROM ranked
                WHERE e.id = ranked.id
                """
            ),
            {"ids": sorted(touched_regs)},
        )

    db.commit()
    return DeriveEventsResult(
        ok=True,
        dry_run=False,
        since=since.isoformat(),
        candidates=len(candidates),
        by_type=by_type,
        deduped=deduped,
        inserted=inserted,
        seq_recomputed_regs=len(touched_regs),
        samples=samples,
    )

