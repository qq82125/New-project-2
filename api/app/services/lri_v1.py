from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AdminConfig, LriScore
from app.repositories.radar import get_admin_config


DEFAULT_MODEL_VERSION = "lri_v1"


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _bin_score(value: int, bins: list[dict[str, Any]]) -> int:
    for b in bins:
        try:
            lte = int(b.get("lte"))
            score = int(b.get("score"))
        except Exception:
            continue
        if value <= lte:
            return score
    return 0


def _risk_level(total_norm: float, levels: list[dict[str, Any]]) -> str:
    # levels are expected descending by gte; we enforce that defensively.
    rows = []
    for r in levels:
        try:
            rows.append((str(r.get("level") or ""), float(r.get("gte"))))
        except Exception:
            continue
    rows.sort(key=lambda x: x[1], reverse=True)
    for level, gte in rows:
        if total_norm >= gte:
            return level or "LOW"
    return "LOW"


def _load_config(db: Session) -> dict[str, Any]:
    cfg = get_admin_config(db, "lri_v1_config")
    if cfg and isinstance(cfg.config_value, dict):
        return dict(cfg.config_value)
    # Fallback minimal defaults (should not happen because migration seeds it).
    return {"enabled": True, "nightly_enabled": False, "max_raw_total": 130, "tte_bins": [], "rh_bins": [], "cd_bins": [], "gp_bins": [], "risk_levels": []}


@dataclass
class LriComputeResult:
    ok: bool
    dry_run: bool
    date: str
    model_version: str
    upsert_mode: bool
    would_write: int
    wrote: int
    risk_dist: dict[str, int]
    missing_methodology_ratio: float
    missing_methodology_count: int
    error: str | None = None


def compute_lri_v1(
    db: Session,
    *,
    asof: date | None = None,
    dry_run: bool = True,
    model_version: str = DEFAULT_MODEL_VERSION,
    upsert_mode: bool = False,
    source_run_id: int | None = None,
) -> LriComputeResult:
    target = asof or _today_utc()
    cfg = _load_config(db)
    if not bool(cfg.get("enabled", True)):
        return LriComputeResult(
            ok=True,
            dry_run=bool(dry_run),
            date=target.isoformat(),
            model_version=str(model_version),
            upsert_mode=bool(upsert_mode),
            would_write=0,
            wrote=0,
            risk_dist={},
            missing_methodology_ratio=0.0,
            missing_methodology_count=0,
        )

    max_raw_total = int(cfg.get("max_raw_total", 130) or 130)
    tte_bins = list(cfg.get("tte_bins") or [])
    rh_bins = list(cfg.get("rh_bins") or [])
    cd_bins = list(cfg.get("cd_bins") or [])
    gp_bins = list(cfg.get("gp_bins") or [])
    risk_levels = list(cfg.get("risk_levels") or [])

    since_365 = target - timedelta(days=365)

    rows = db.execute(
        text(
            """
            WITH rep_prod AS (
              SELECT DISTINCT ON (p.registration_id)
                p.registration_id,
                p.id AS product_id,
                COALESCE(NULLIF(btrim(p.ivd_category), ''), NULLIF(btrim(p.category), '')) AS ivd_category
              FROM products p
              WHERE p.is_ivd IS TRUE AND p.registration_id IS NOT NULL
              ORDER BY p.registration_id, p.updated_at DESC NULLS LAST, p.created_at DESC, p.id ASC
            ),
            rep_meth AS (
              SELECT
                pm.product_id,
                pm.methodology_id,
                pm.confidence,
                ROW_NUMBER() OVER (
                  PARTITION BY pm.product_id
                  ORDER BY pm.confidence DESC, pm.created_at ASC, pm.id ASC
                )::int AS rn
              FROM product_methodology_map pm
            ),
            prod_dim AS (
              SELECT
                rp.registration_id,
                rp.product_id,
                rp.ivd_category,
                rm.methodology_id
              FROM rep_prod rp
              LEFT JOIN rep_meth rm
                ON rm.product_id = rp.product_id AND rm.rn = 1
            ),
            reg_dim AS (
              SELECT
                r.id AS registration_id,
                pd.product_id,
                pd.methodology_id,
                pd.ivd_category,
                r.expiry_date,
                COALESCE(r.approval_date, (r.created_at AT TIME ZONE 'UTC')::date) AS first_seen_date
              FROM registrations r
              LEFT JOIN prod_dim pd ON pd.registration_id = r.id
            ),
            comp AS (
              SELECT
                methodology_id,
                ivd_category,
                COUNT(DISTINCT registration_id)::int AS competitive_count
              FROM reg_dim
              WHERE methodology_id IS NOT NULL AND ivd_category IS NOT NULL
              GROUP BY methodology_id, ivd_category
            ),
            gp AS (
              SELECT
                methodology_id,
                ivd_category,
                COUNT(DISTINCT registration_id)::int AS gp_new_12m
              FROM reg_dim
              WHERE methodology_id IS NOT NULL AND ivd_category IS NOT NULL
                AND first_seen_date >= :since_365 AND first_seen_date <= :asof
              GROUP BY methodology_id, ivd_category
            ),
            rh AS (
              SELECT
                registration_id,
                COUNT(1)::int AS renewal_count
              FROM registration_events
              WHERE event_type IN ('renew', 'RENEWAL', 'renewal', 'RENEW')
              GROUP BY registration_id
            )
            SELECT
              rd.registration_id,
              rd.product_id,
              rd.methodology_id,
              rd.ivd_category,
              rd.expiry_date,
              COALESCE(rh.renewal_count, 0)::int AS renewal_count,
              COALESCE(comp.competitive_count, 0)::int AS competitive_count,
              COALESCE(gp.gp_new_12m, 0)::int AS gp_new_12m
            FROM reg_dim rd
            LEFT JOIN rh ON rh.registration_id = rd.registration_id
            LEFT JOIN comp ON comp.methodology_id = rd.methodology_id AND comp.ivd_category = rd.ivd_category
            LEFT JOIN gp ON gp.methodology_id = rd.methodology_id AND gp.ivd_category = rd.ivd_category
            """
        ),
        {"since_365": since_365, "asof": target},
    ).mappings().all()

    risk_dist: dict[str, int] = {}
    missing_methodology = 0
    out_rows: list[dict[str, Any]] = []

    for r in rows:
        expiry = r.get("expiry_date")
        tte_days = None
        try:
            if expiry is not None:
                tte_days = int((expiry - target).days)
        except Exception:
            tte_days = None

        renewal_count = int(r.get("renewal_count") or 0)
        competitive_count = int(r.get("competitive_count") or 0)
        gp_new_12m = int(r.get("gp_new_12m") or 0)

        methodology_id = r.get("methodology_id")
        if methodology_id is None:
            missing_methodology += 1
            competitive_count = 0
            gp_new_12m = 0

        tte_score = _bin_score(int(tte_days if tte_days is not None else 99999), tte_bins) if tte_bins else 0
        rh_score = _bin_score(int(renewal_count), rh_bins) if rh_bins else 0
        cd_score = _bin_score(int(competitive_count), cd_bins) if cd_bins else 0
        gp_score = _bin_score(int(gp_new_12m), gp_bins) if gp_bins else 0
        lri_total = int(tte_score + rh_score + cd_score + gp_score)
        lri_norm = (float(lri_total) / float(max_raw_total) * 100.0) if max_raw_total > 0 else 0.0
        risk_level = _risk_level(lri_norm, risk_levels) if risk_levels else "LOW"

        risk_dist[risk_level] = int(risk_dist.get(risk_level, 0) or 0) + 1

        out_rows.append(
            {
                "registration_id": r["registration_id"],
                "product_id": r.get("product_id"),
                "methodology_id": methodology_id,
                "tte_days": tte_days,
                "renewal_count": renewal_count,
                "competitive_count": competitive_count,
                "gp_new_12m": gp_new_12m,
                "tte_score": tte_score,
                "rh_score": rh_score,
                "cd_score": cd_score,
                "gp_score": gp_score,
                "lri_total": lri_total,
                "lri_norm": lri_norm,
                "risk_level": risk_level,
            }
        )

    total = len(out_rows)
    missing_ratio = float(missing_methodology / total) if total > 0 else 0.0
    if dry_run:
        return LriComputeResult(
            ok=True,
            dry_run=True,
            date=target.isoformat(),
            model_version=str(model_version),
            upsert_mode=bool(upsert_mode),
            would_write=total,
            wrote=0,
            risk_dist=risk_dist,
            missing_methodology_ratio=missing_ratio,
            missing_methodology_count=int(missing_methodology),
        )

    # Optional upsert-by-day: delete existing rows for this logical date window + model_version.
    if upsert_mode:
        start_dt = datetime.combine(target, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(days=1)
        db.execute(
            text(
                """
                DELETE FROM lri_scores
                WHERE model_version = :mv
                  AND calculated_at >= :start_dt
                  AND calculated_at < :end_dt
                """
            ),
            {"mv": str(model_version), "start_dt": start_dt, "end_dt": end_dt},
        )

    wrote = 0
    for row in out_rows:
        stmt = insert(LriScore).values(
            registration_id=row["registration_id"],
            product_id=row.get("product_id"),
            methodology_id=row.get("methodology_id"),
            tte_days=row.get("tte_days"),
            renewal_count=int(row.get("renewal_count") or 0),
            competitive_count=int(row.get("competitive_count") or 0),
            gp_new_12m=int(row.get("gp_new_12m") or 0),
            tte_score=int(row.get("tte_score") or 0),
            rh_score=int(row.get("rh_score") or 0),
            cd_score=int(row.get("cd_score") or 0),
            gp_score=int(row.get("gp_score") or 0),
            lri_total=int(row.get("lri_total") or 0),
            lri_norm=float(row.get("lri_norm") or 0.0),
            risk_level=str(row.get("risk_level") or "LOW"),
            model_version=str(model_version),
            calculated_at=datetime.now(timezone.utc),
            source_run_id=(int(source_run_id) if source_run_id is not None else None),
        )
        db.execute(stmt)
        wrote += 1

    # Update daily_metrics with run-quality indicators (ops stability).
    try:
        from app.services.metrics import upsert_daily_lri_quality_metrics

        upsert_daily_lri_quality_metrics(
            db,
            metric_date=target,
            lri_computed_count=int(wrote),
            lri_missing_methodology_count=int(missing_methodology),
            risk_level_distribution=risk_dist,
        )
    except Exception:
        # Never block LRI compute because of ops-metrics writes.
        pass

    db.commit()
    return LriComputeResult(
        ok=True,
        dry_run=False,
        date=target.isoformat(),
        model_version=str(model_version),
        upsert_mode=bool(upsert_mode),
        would_write=total,
        wrote=wrote,
        risk_dist=risk_dist,
        missing_methodology_ratio=missing_ratio,
        missing_methodology_count=int(missing_methodology),
    )


def compute_lri_v1_if_due(db: Session, *, asof: date | None = None, model_version: str = DEFAULT_MODEL_VERSION) -> dict[str, Any]:
    """Nightly helper: compute once per day if enabled and not already computed."""
    target = asof or _today_utc()
    cfg = _load_config(db)
    if not bool(cfg.get("enabled", True)) or not bool(cfg.get("nightly_enabled", False)):
        return {"ok": True, "skipped": True, "reason": "disabled"}

    start_dt = datetime.combine(target, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    exists = db.execute(
        text(
            """
            SELECT 1
            FROM lri_scores
            WHERE model_version = :mv
              AND calculated_at >= :start_dt
              AND calculated_at < :end_dt
            LIMIT 1
            """
        ),
        {"mv": str(model_version), "start_dt": start_dt, "end_dt": end_dt},
    ).scalar()
    if exists:
        return {"ok": True, "skipped": True, "reason": "already_computed", "date": target.isoformat()}

    res = compute_lri_v1(db, asof=target, dry_run=False, model_version=model_version, upsert_mode=True)
    return {"ok": bool(res.ok), "skipped": False, "date": target.isoformat(), "wrote": int(res.wrote), "risk_dist": res.risk_dist}
