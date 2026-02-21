from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import DailyQualityMetric
from app.services.normalize_keys import normalize_registration_no
from app.services.registration_no_parser import parse_registration_no

_METRIC_KEYS: tuple[str, ...] = (
    "regno_parse_ok_rate",
    "regno_unknown_rate",
    "legacy_share",
    "diff_success_rate",
    "udi_pending_count",
    "field_evidence_coverage_rate",
)

_CRITICAL_META_FIELDS: tuple[str, ...] = ("approval_date", "expiry_date", "status", "filing_no")


@dataclass
class QualityMetricEntry:
    value: float
    meta: dict[str, Any]


@dataclass
class DailyQualityReport:
    as_of: date
    metrics: dict[str, QualityMetricEntry]

    def as_json(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "metrics": {
                key: {
                    "value": round(float(entry.value), 6),
                    "meta": dict(entry.meta or {}),
                }
                for key, entry in self.metrics.items()
            },
        }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _day_end(target: date) -> date:
    return target + timedelta(days=1)


def _window_start(as_of: date, *, window_days: int) -> date:
    days = max(1, int(window_days))
    return as_of - timedelta(days=days - 1)


def _has_registration_semantic_columns(db: Session) -> bool:
    cols = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='registrations'
              AND column_name IN ('parse_ok', 'regno_type', 'is_legacy_format')
            """
        )
    ).fetchall()
    got = {str(r[0]) for r in cols}
    return {"parse_ok", "regno_type", "is_legacy_format"}.issubset(got)


def _compute_regno_metrics(db: Session, *, as_of: date, window_days: int) -> dict[str, QualityMetricEntry]:
    window_start = _window_start(as_of, window_days=window_days)
    day_end = _day_end(as_of)
    if _has_registration_semantic_columns(db):
        row = (
            db.execute(
                text(
                    """
                    SELECT
                      COUNT(1) AS total,
                      SUM(CASE WHEN parse_ok IS TRUE THEN 1 ELSE 0 END) AS parse_ok_count,
                      SUM(CASE WHEN COALESCE(regno_type, 'unknown') = 'unknown' THEN 1 ELSE 0 END) AS unknown_count,
                      SUM(CASE WHEN is_legacy_format IS TRUE THEN 1 ELSE 0 END) AS legacy_count
                    FROM registrations
                    WHERE created_at >= :window_start
                      AND created_at < :day_end
                    """
                ),
                {"day_end": day_end, "window_start": window_start},
            )
            .mappings()
            .first()
            or {}
        )
        total = int(row.get("total") or 0)
        parse_ok_count = int(row.get("parse_ok_count") or 0)
        unknown_count = int(row.get("unknown_count") or 0)
        legacy_count = int(row.get("legacy_count") or 0)
    else:
        rows = db.execute(
            text(
                """
                SELECT registration_no
                FROM registrations
                WHERE created_at >= :window_start
                  AND created_at < :day_end
                """
            ),
            {"day_end": day_end, "window_start": window_start},
        ).fetchall()
        total = len(rows)
        parse_ok_count = 0
        unknown_count = 0
        legacy_count = 0
        for row in rows:
            reg_no = normalize_registration_no(str(row[0] or ""))
            parsed = parse_registration_no(reg_no)
            if parsed.parse_ok:
                parse_ok_count += 1
            if parsed.regno_type == "unknown":
                unknown_count += 1
            if parsed.is_legacy_format:
                legacy_count += 1

    return {
        "regno_parse_ok_rate": QualityMetricEntry(
            value=_ratio(parse_ok_count, total),
            meta={"total": total, "parse_ok_count": parse_ok_count, "window_days": int(window_days)},
        ),
        "regno_unknown_rate": QualityMetricEntry(
            value=_ratio(unknown_count, total),
            meta={"total": total, "unknown_count": unknown_count, "window_days": int(window_days)},
        ),
        "legacy_share": QualityMetricEntry(
            value=_ratio(legacy_count, total),
            meta={"total": total, "legacy_count": legacy_count, "window_days": int(window_days)},
        ),
    }


def _compute_diff_success_rate(db: Session, *, as_of: date) -> QualityMetricEntry:
    failed = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM shadow_diff_errors
                WHERE created_at >= :d
                  AND created_at < :d + INTERVAL '1 day'
                """
            ),
            {"d": as_of},
        ).scalar()
        or 0
    )
    success = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM nmpa_snapshots
                WHERE snapshot_date = :d
                """
            ),
            {"d": as_of},
        ).scalar()
        or 0
    )
    top_reasons = [
        {"reason_code": str(r[0]), "count": int(r[1])}
        for r in db.execute(
            text(
                """
                SELECT reason_code, COUNT(1) AS cnt
                FROM shadow_diff_errors
                WHERE created_at >= :d
                  AND created_at < :d + INTERVAL '1 day'
                GROUP BY reason_code
                ORDER BY cnt DESC, reason_code ASC
                LIMIT 5
                """
            ),
            {"d": as_of},
        ).fetchall()
    ]
    denom = success + failed
    return QualityMetricEntry(
        value=_ratio(success, denom),
        meta={"success": success, "failed": failed, "top_reason_codes": top_reasons},
    )


def _compute_udi_pending_count(db: Session) -> QualityMetricEntry:
    cnt = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM pending_udi_links
                WHERE status IN ('PENDING', 'RETRYING', 'OPEN', 'pending', 'retrying', 'open')
                """
            )
        ).scalar()
        or 0
    )
    return QualityMetricEntry(value=float(cnt), meta={"pending_count": cnt})


def _compute_field_evidence_coverage_rate(db: Session, *, as_of: date, window_days: int) -> QualityMetricEntry:
    window_start = _window_start(as_of, window_days=window_days)
    day_end = _day_end(as_of)
    total = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM registrations
                WHERE created_at >= :window_start
                  AND created_at < :day_end
                """
            ),
            {"day_end": day_end, "window_start": window_start},
        ).scalar()
        or 0
    )
    field_cov: dict[str, float] = {}
    field_cnt: dict[str, int] = {}
    for field in _CRITICAL_META_FIELDS:
        cnt = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM registrations
                    WHERE created_at >= :window_start
                      AND created_at < :day_end
                      AND jsonb_typeof(field_meta -> :field_name) = 'object'
                    """
                ),
                {"day_end": day_end, "window_start": window_start, "field_name": field},
            ).scalar()
            or 0
        )
        field_cnt[field] = cnt
        field_cov[field] = _ratio(cnt, total)

    if field_cov:
        coverage_rate = round(sum(field_cov.values()) / float(len(field_cov)), 6)
    else:
        coverage_rate = 0.0
    return QualityMetricEntry(
        value=coverage_rate,
        meta={
            "total_registrations": total,
            "window_days": int(window_days),
            "fields": list(_CRITICAL_META_FIELDS),
            "field_counts": field_cnt,
            "field_rates": field_cov,
        },
    )


def compute_daily_quality_metrics(db: Session, *, as_of: date, window_days: int = 365) -> DailyQualityReport:
    metrics: dict[str, QualityMetricEntry] = {}
    metrics.update(_compute_regno_metrics(db, as_of=as_of, window_days=window_days))
    metrics["diff_success_rate"] = _compute_diff_success_rate(db, as_of=as_of)
    metrics["udi_pending_count"] = _compute_udi_pending_count(db)
    metrics["field_evidence_coverage_rate"] = _compute_field_evidence_coverage_rate(
        db,
        as_of=as_of,
        window_days=window_days,
    )

    # Keep output contract stable and explicit.
    for key in _METRIC_KEYS:
        metrics.setdefault(key, QualityMetricEntry(value=0.0, meta={"fallback": True}))
    return DailyQualityReport(as_of=as_of, metrics=metrics)


def upsert_daily_quality_metrics(db: Session, report: DailyQualityReport) -> None:
    for key, entry in report.metrics.items():
        stmt = insert(DailyQualityMetric).values(
            metric_date=report.as_of,
            metric_key=str(key),
            value=Decimal(str(round(float(entry.value), 6))),
            meta=dict(entry.meta or {}),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyQualityMetric.metric_date, DailyQualityMetric.metric_key],
            set_={
                "value": Decimal(str(round(float(entry.value), 6))),
                "meta": dict(entry.meta or {}),
            },
        )
        db.execute(stmt)
