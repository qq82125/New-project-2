from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class UdiOutlierItem:
    reg_no: str
    di_count: int

    @property
    def to_dict(self) -> dict[str, Any]:
        return {"registration_no": self.reg_no, "di_count": self.di_count}


@dataclass
class UdiMultiBindItem:
    di: str
    regno_count: int
    registration_nos: list[str]

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "di": self.di,
            "regno_count": int(self.regno_count),
            "registration_nos": list(self.registration_nos),
        }


def find_udi_outliers(
    db: Session,
    *,
    threshold: int,
    source_run_id: int | None = None,
    limit: int = 100,
) -> list[UdiOutlierItem]:
    where = [
        "registration_no_norm IS NOT NULL",
        "btrim(registration_no_norm) <> ''",
    ]
    params: dict[str, Any] = {"threshold": int(threshold), "lim": int(limit)}
    if source_run_id is not None:
        where.append("source_run_id = :srid")
        params["srid"] = int(source_run_id)

    rows = db.execute(
        text(
            f"""
            SELECT registration_no_norm AS reg_no, COUNT(1)::bigint AS di_count
            FROM udi_device_index
            WHERE {" AND ".join(where)}
            GROUP BY registration_no_norm
            HAVING COUNT(1) > :threshold
            ORDER BY di_count DESC, registration_no_norm ASC
            LIMIT :lim
            """
        ),
        params,
    ).mappings().all()
    return [UdiOutlierItem(reg_no=str(r.get("reg_no") or ""), di_count=int(r.get("di_count") or 0)) for r in rows]


def find_udi_outliers_effective(
    db: Session,
    *,
    threshold: int,
    source_run_id: int | None = None,
    limit: int = 100,
) -> tuple[list[UdiOutlierItem], bool]:
    """
    Effective (post-governance) outliers, prioritized from product_variants facts.

    Returns (items, limited_by_run):
    - limited_by_run=True only when we can reliably scope by source_run_id.
    - product_variants currently has no source_run_id; fallback is global current facts.
    """
    # NOTE: no source_run_id in product_variants; keep this explicit for audit explainability.
    limited_by_run = False
    rows = db.execute(
        text(
            """
            SELECT registry_no AS reg_no, COUNT(DISTINCT di)::bigint AS di_count
            FROM product_variants
            WHERE registry_no IS NOT NULL
              AND btrim(registry_no) <> ''
              AND di IS NOT NULL
              AND btrim(di) <> ''
            GROUP BY registry_no
            HAVING COUNT(DISTINCT di) > :threshold
            ORDER BY di_count DESC, registry_no ASC
            LIMIT :lim
            """
        ),
        {"threshold": int(threshold), "lim": int(limit)},
    ).mappings().all()
    return (
        [UdiOutlierItem(reg_no=str(r.get("reg_no") or ""), di_count=int(r.get("di_count") or 0)) for r in rows],
        limited_by_run,
    )


def find_udi_multi_bind_dis(
    db: Session,
    *,
    source_run_id: int | None = None,
    limit: int = 100,
) -> list[UdiMultiBindItem]:
    where = [
        "di_norm IS NOT NULL",
        "btrim(di_norm) <> ''",
        "registration_no_norm IS NOT NULL",
        "btrim(registration_no_norm) <> ''",
    ]
    params: dict[str, Any] = {"lim": int(limit)}
    if source_run_id is not None:
        where.append("source_run_id = :srid")
        params["srid"] = int(source_run_id)

    rows = db.execute(
        text(
            f"""
            SELECT
              di_norm AS di,
              COUNT(DISTINCT registration_no_norm)::bigint AS regno_count,
              ARRAY_AGG(DISTINCT registration_no_norm ORDER BY registration_no_norm) AS regnos
            FROM udi_device_index
            WHERE {" AND ".join(where)}
            GROUP BY di_norm
            HAVING COUNT(DISTINCT registration_no_norm) > 1
            ORDER BY regno_count DESC, di_norm ASC
            LIMIT :lim
            """
        ),
        params,
    ).mappings().all()
    out: list[UdiMultiBindItem] = []
    for r in rows:
        regnos = r.get("regnos") or []
        if not isinstance(regnos, list):
            regnos = list(regnos)
        out.append(
            UdiMultiBindItem(
                di=str(r.get("di") or ""),
                regno_count=int(r.get("regno_count") or 0),
                registration_nos=[str(x) for x in regnos if str(x).strip()],
            )
        )
    return out


def find_udi_multi_bind_dis_effective(
    db: Session,
    *,
    source_run_id: int | None = None,
    limit: int = 100,
) -> tuple[list[UdiMultiBindItem], bool]:
    # NOTE: product_variants currently has no source_run_id; fallback is global current facts.
    limited_by_run = False
    rows = db.execute(
        text(
            """
            SELECT
              di,
              COUNT(DISTINCT registry_no)::bigint AS regno_count,
              ARRAY_AGG(DISTINCT registry_no ORDER BY registry_no) AS regnos
            FROM product_variants
            WHERE di IS NOT NULL
              AND btrim(di) <> ''
              AND registry_no IS NOT NULL
              AND btrim(registry_no) <> ''
            GROUP BY di
            HAVING COUNT(DISTINCT registry_no) > 1
            ORDER BY regno_count DESC, di ASC
            LIMIT :lim
            """
        ),
        {"lim": int(limit)},
    ).mappings().all()
    out: list[UdiMultiBindItem] = []
    for r in rows:
        regnos = r.get("regnos") or []
        if not isinstance(regnos, list):
            regnos = list(regnos)
        out.append(
            UdiMultiBindItem(
                di=str(r.get("di") or ""),
                regno_count=int(r.get("regno_count") or 0),
                registration_nos=[str(x) for x in regnos if str(x).strip()],
            )
        )
    return out, limited_by_run


def compute_udi_outlier_distribution(
    db: Session,
    *,
    source_run_id: int | None = None,
) -> dict[str, Any]:
    where = [
        "registration_no_norm IS NOT NULL",
        "btrim(registration_no_norm) <> ''",
    ]
    params: dict[str, Any] = {}
    if source_run_id is not None:
        where.append("source_run_id = :srid")
        params["srid"] = int(source_run_id)

    dist = db.execute(
        text(
            f"""
            WITH per_reg AS (
              SELECT registration_no_norm AS reg_no, COUNT(1)::bigint AS di_count
              FROM udi_device_index
              WHERE {" AND ".join(where)}
              GROUP BY registration_no_norm
            )
            SELECT
              COALESCE(COUNT(1), 0)::bigint AS registration_count,
              COALESCE(SUM(di_count), 0)::bigint AS total_di_bound,
              COALESCE(MIN(di_count), 0)::bigint AS min_di,
              COALESCE(MAX(di_count), 0)::bigint AS max_di,
              COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p50,
              COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p90,
              COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p99
            FROM per_reg
            """
        ),
        params,
    ).mappings().one()

    unbound_where = ["registration_no_norm IS NULL OR btrim(registration_no_norm) = ''"]
    if source_run_id is not None:
        unbound_where.append("source_run_id = :srid")
    unbound_di = int(
        db.execute(
            text(f"SELECT COUNT(1) FROM udi_device_index WHERE {' AND '.join(unbound_where)}"),
            params,
        ).scalar()
        or 0
    )
    return {
        "registration_count": int(dist.get("registration_count") or 0),
        "total_di_bound": int(dist.get("total_di_bound") or 0),
        "min": int(dist.get("min_di") or 0),
        "max": int(dist.get("max_di") or 0),
        "p50": float(dist.get("p50") or 0),
        "p90": float(dist.get("p90") or 0),
        "p99": float(dist.get("p99") or 0),
        "di_unbound_registration_count": int(unbound_di),
    }


def compute_udi_outlier_distribution_effective(
    db: Session,
    *,
    source_run_id: int | None = None,
) -> tuple[dict[str, Any], bool]:
    """
    Effective (post-governance) DI distribution from product_variants.
    """
    # NOTE: product_variants currently has no source_run_id; fallback is global current facts.
    limited_by_run = False
    dist = db.execute(
        text(
            """
            WITH per_reg AS (
              SELECT registry_no AS reg_no, COUNT(DISTINCT di)::bigint AS di_count
              FROM product_variants
              WHERE registry_no IS NOT NULL
                AND btrim(registry_no) <> ''
                AND di IS NOT NULL
                AND btrim(di) <> ''
              GROUP BY registry_no
            )
            SELECT
              COALESCE(COUNT(1), 0)::bigint AS registration_count,
              COALESCE(SUM(di_count), 0)::bigint AS total_di_bound,
              COALESCE(MIN(di_count), 0)::bigint AS min_di,
              COALESCE(MAX(di_count), 0)::bigint AS max_di,
              COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p50,
              COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p90,
              COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p99
            FROM per_reg
            """
        )
    ).mappings().one()

    return (
        {
            "registration_count": int(dist.get("registration_count") or 0),
            "total_di_bound": int(dist.get("total_di_bound") or 0),
            "min": int(dist.get("min_di") or 0),
            "max": int(dist.get("max_di") or 0),
            "p50": float(dist.get("p50") or 0),
            "p90": float(dist.get("p90") or 0),
            "p99": float(dist.get("p99") or 0),
            "di_unbound_registration_count": 0,
        },
        limited_by_run,
    )


def materialize_udi_outliers(
    db: Session,
    *,
    source_run_id: int | None,
    threshold: int,
    items: list[UdiOutlierItem],
) -> int:
    wrote = 0
    for item in items:
        if not item.reg_no:
            continue
        inserted = db.execute(
            text(
                """
                INSERT INTO udi_outliers (source_run_id, reg_no, di_count, threshold, detected_at, status, notes)
                VALUES (:srid, :reg_no, :di_count, :threshold, NOW(), 'open', NULL)
                ON CONFLICT (source_run_id, reg_no) DO NOTHING
                RETURNING id
                """
            ),
            {
                "srid": (int(source_run_id) if source_run_id is not None else None),
                "reg_no": item.reg_no,
                "di_count": int(item.di_count),
                "threshold": int(threshold),
            },
        ).scalar()
        if inserted is not None:
            wrote += 1
    return wrote
