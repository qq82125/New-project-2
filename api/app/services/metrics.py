from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    ChangeLog,
    DailyMetric,
    DailyUdiMetric,
    PendingDocument,
    PendingUdiLink,
    Product,
    ProductParam,
    ProductVariant,
    ProductUdiMap,
    SourceRun,
    Subscription,
    UdiDiMaster,
)


def _count_change_type(db: Session, metric_date: date, change_type: str) -> int:
    stmt = (
        select(func.count(ChangeLog.id))
        .join(Product, Product.id == ChangeLog.product_id)
        .where(
            ChangeLog.change_date >= metric_date,
            ChangeLog.change_date < metric_date + timedelta(days=1),
            ChangeLog.change_type == change_type,
            Product.is_ivd.is_(True),
        )
    )
    return int(db.scalar(stmt) or 0)


def _count_expiring_in_90d(db: Session, metric_date: date) -> int:
    upper = metric_date + timedelta(days=90)
    stmt = select(func.count(Product.id)).where(
        Product.expiry_date.is_not(None),
        Product.expiry_date >= metric_date,
        Product.expiry_date <= upper,
        Product.status != 'cancelled',
        Product.is_ivd.is_(True),
    )
    return int(db.scalar(stmt) or 0)


def _count_active_subscriptions(db: Session) -> int:
    stmt = select(func.count(Subscription.id)).where(Subscription.is_active.is_(True))
    return int(db.scalar(stmt) or 0)


def _latest_source_run_id(db: Session, metric_date: date) -> int | None:
    stmt = (
        select(SourceRun.id)
        .where(SourceRun.started_at >= metric_date, SourceRun.started_at < metric_date + timedelta(days=1))
        .order_by(SourceRun.started_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def _count_total_di(db: Session) -> int:
    # Preferred source is udi_di_master; fallback to indexed UDI DI coverage when master is not fully backfilled.
    # This avoids impossible states where mapped_di_count >> total_di_count.
    try:
        master_total = int(db.scalar(select(func.count(UdiDiMaster.id))) or 0)
    except Exception:
        # Unit tests may pass a lightweight FakeDB without SQLAlchemy APIs.
        master_total = 0
    try:
        index_total = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT di_norm)
                    FROM udi_device_index
                    WHERE di_norm IS NOT NULL AND btrim(di_norm) <> ''
                    """
                )
            ).scalar()
            or 0
        )
    except Exception:
        index_total = 0
    return max(master_total, index_total)


def _count_mapped_di(db: Session) -> int:
    # product_udi_map can contain multiple rows for same DI historically; dedupe on DI for coverage.
    try:
        return int(db.scalar(select(func.count(func.distinct(ProductUdiMap.di)))) or 0)
    except Exception:
        return 0


def _count_unmapped_di_pending(db: Session) -> int:
    # Pending queue status is uppercase in pending_udi_links; keep open alias for compatibility.
    try:
        return int(
            db.scalar(
                select(func.count(func.distinct(PendingUdiLink.di))).where(
                    PendingUdiLink.status.in_(('PENDING', 'OPEN', 'pending', 'open'))
                )
            )
            or 0
        )
    except Exception:
        return 0


def _count_pending_documents(db: Session) -> int:
    try:
        return int(db.scalar(select(func.count(PendingDocument.id)).where(PendingDocument.status == 'pending')) or 0)
    except Exception:
        return 0


def _compute_udi_value_add_metrics(db: Session, metric_date: date) -> dict:
    """Compute UDI 'coverage + value-add' metrics for daily_metrics.udi_metrics.

    Metrics are designed to answer two questions at a glance:
    - Coverage: how much of UDI is usable (DI/reg/cert/packing/storage)?
    - Value-add: how much enrichment was produced (stubs/variants/params)?
    """
    # Identify UDI indexing runs for the day (supports multiple run sources).
    run_ids = [
        int(x)
        for (x,) in db.execute(
            text(
                """
                SELECT id
                FROM source_runs
                WHERE started_at >= :d
                  AND started_at < :d + INTERVAL '1 day'
                  AND upper(source) LIKE 'UDI_INDEX%'
                ORDER BY started_at ASC
                """
            ),
            {"d": metric_date},
        ).fetchall()
    ]

    if not run_ids:
        return {
            "udi_devices_indexed": 0,
            "udi_di_non_empty_rate": 0.0,
            "udi_reg_non_empty_rate": 0.0,
            "udi_has_cert_yes_rate": 0.0,
            "udi_unique_reg": 0,
            "udi_stub_created": 0,
            "udi_variants_upserted": 0,
            "udi_packings_present_rate": 0.0,
            "udi_storages_present_rate": 0.0,
            "udi_params_written": 0,
            "udi_index_run_ids": [],
        }

    row = (
        db.execute(
            text(
                """
                SELECT
                  COUNT(1) AS total,
                  SUM(CASE WHEN btrim(di_norm) <> '' THEN 1 ELSE 0 END) AS di_non_empty,
                  SUM(CASE WHEN registration_no_norm IS NOT NULL AND btrim(registration_no_norm) <> '' THEN 1 ELSE 0 END) AS reg_non_empty,
                  SUM(CASE WHEN has_cert IS TRUE THEN 1 ELSE 0 END) AS has_cert_yes,
                  SUM(CASE WHEN packing_json IS NOT NULL AND packing_json::text <> '[]' THEN 1 ELSE 0 END) AS packings_present,
                  SUM(CASE WHEN storage_json IS NOT NULL AND storage_json::text <> '[]' THEN 1 ELSE 0 END) AS storages_present,
                  COUNT(DISTINCT CASE WHEN registration_no_norm IS NOT NULL AND btrim(registration_no_norm) <> '' THEN registration_no_norm END) AS unique_reg
                FROM udi_device_index
                WHERE source_run_id = ANY(:ids)
                """
            ),
            {"ids": run_ids},
        )
        .mappings()
        .first()
        or {}
    )

    total = int(row.get("total") or 0)
    di_non_empty = int(row.get("di_non_empty") or 0)
    reg_non_empty = int(row.get("reg_non_empty") or 0)
    has_cert_yes = int(row.get("has_cert_yes") or 0)
    packings_present = int(row.get("packings_present") or 0)
    storages_present = int(row.get("storages_present") or 0)
    unique_reg = int(row.get("unique_reg") or 0)

    def _rate(n: int, d: int) -> float:
        return round(float(n) / float(d), 6) if d > 0 else 0.0

    # "Value-add" counters (independent of udi_device_index run IDs).
    stub_created = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM products
                WHERE created_at >= :d
                  AND created_at < :d + INTERVAL '1 day'
                  AND (raw_json ? '_stub')
                  AND COALESCE(raw_json->'_stub'->>'source_hint', '') = 'UDI'
                """
            ),
            {"d": metric_date},
        ).scalar()
        or 0
    )

    variants_upserted = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM product_variants
                WHERE updated_at >= :d
                  AND updated_at < :d + INTERVAL '1 day'
                  AND registration_id IS NOT NULL
                  AND evidence_raw_document_id IS NOT NULL
                """
            ),
            {"d": metric_date},
        ).scalar()
        or 0
    )

    params_written = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM product_params
                WHERE created_at >= :d
                  AND created_at < :d + INTERVAL '1 day'
                  AND extract_version = 'udi_params_v1'
                """
            ),
            {"d": metric_date},
        ).scalar()
        or 0
    )

    return {
        "udi_devices_indexed": total,
        "udi_di_non_empty_rate": _rate(di_non_empty, total),
        "udi_reg_non_empty_rate": _rate(reg_non_empty, total),
        "udi_has_cert_yes_rate": _rate(has_cert_yes, total),
        "udi_unique_reg": unique_reg,
        "udi_stub_created": stub_created,
        "udi_variants_upserted": variants_upserted,
        "udi_packings_present_rate": _rate(packings_present, total),
        "udi_storages_present_rate": _rate(storages_present, total),
        "udi_params_written": params_written,
        "udi_index_run_ids": run_ids,
    }


def upsert_daily_lri_quality_metrics(
    db: Session,
    *,
    metric_date: date,
    lri_computed_count: int,
    lri_missing_methodology_count: int,
    risk_level_distribution: dict[str, int] | None,
) -> None:
    # Ensure stable shape for dashboards/digests.
    dist0 = {k: int((risk_level_distribution or {}).get(k, 0) or 0) for k in ("LOW", "MID", "HIGH", "CRITICAL")}
    pending_count = _count_pending_documents(db)

    stmt = insert(DailyMetric).values(
        metric_date=metric_date,
        new_products=0,
        updated_products=0,
        cancelled_products=0,
        expiring_in_90d=0,
        active_subscriptions=0,
        pending_count=int(pending_count),
        lri_computed_count=int(lri_computed_count),
        lri_missing_methodology_count=int(lri_missing_methodology_count),
        risk_level_distribution=dist0,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyMetric.metric_date],
        set_={
            'pending_count': int(pending_count),
            'lri_computed_count': int(lri_computed_count),
            'lri_missing_methodology_count': int(lri_missing_methodology_count),
            'risk_level_distribution': dist0,
        },
    )
    db.execute(stmt)


def generate_daily_metrics(db: Session, metric_date: date | None = None) -> DailyMetric:
    target_date = metric_date or date.today()

    new_products = _count_change_type(db, target_date, 'new')
    updated_products = _count_change_type(db, target_date, 'update')
    cancelled_products = _count_change_type(db, target_date, 'cancel') + _count_change_type(db, target_date, 'expire')
    expiring_in_90d = _count_expiring_in_90d(db, target_date)
    active_subscriptions = _count_active_subscriptions(db)
    source_run_id = _latest_source_run_id(db, target_date)
    total_di_count = _count_total_di(db)
    mapped_di_count = _count_mapped_di(db)
    unmapped_di_count = _count_unmapped_di_pending(db)
    ratio_raw = (float(mapped_di_count) / float(total_di_count)) if total_di_count > 0 else 0.0
    # Keep ratio within [0,1] to match contract and avoid numeric overflow on write.
    coverage_ratio = max(0.0, min(1.0, ratio_raw))
    udi_metrics = _compute_udi_value_add_metrics(db, target_date)

    stmt = insert(DailyMetric).values(
        metric_date=target_date,
        new_products=new_products,
        updated_products=updated_products,
        cancelled_products=cancelled_products,
        expiring_in_90d=expiring_in_90d,
        active_subscriptions=active_subscriptions,
        source_run_id=source_run_id,
        udi_metrics=udi_metrics,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[DailyMetric.metric_date],
        set_={
            'new_products': new_products,
            'updated_products': updated_products,
            'cancelled_products': cancelled_products,
            'expiring_in_90d': expiring_in_90d,
            'active_subscriptions': active_subscriptions,
            'source_run_id': source_run_id,
            'udi_metrics': udi_metrics,
        },
    )
    db.execute(stmt)

    udi_stmt = insert(DailyUdiMetric).values(
        metric_date=target_date,
        total_di_count=total_di_count,
        mapped_di_count=mapped_di_count,
        unmapped_di_count=unmapped_di_count,
        coverage_ratio=coverage_ratio,
        source_run_id=source_run_id,
    )
    udi_stmt = udi_stmt.on_conflict_do_update(
        index_elements=[DailyUdiMetric.metric_date],
        set_={
            'total_di_count': total_di_count,
            'mapped_di_count': mapped_di_count,
            'unmapped_di_count': unmapped_di_count,
            'coverage_ratio': coverage_ratio,
            'source_run_id': source_run_id,
        },
    )
    db.execute(udi_stmt)
    db.commit()

    row = db.get(DailyMetric, target_date)
    if row is None:
        raise RuntimeError('failed to upsert daily_metrics')
    return row


def regenerate_daily_metrics(db: Session, *, days: int = 365, end_date: date | None = None) -> list[str]:
    if days <= 0:
        return []
    end0 = end_date or date.today()
    start0 = end0 - timedelta(days=days - 1)
    out: list[str] = []
    cur = start0
    while cur <= end0:
        row = generate_daily_metrics(db, cur)
        out.append(row.metric_date.isoformat())
        cur = cur + timedelta(days=1)
    return out
