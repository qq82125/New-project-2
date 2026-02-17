#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import ChangeLog, Product, ProductVariant, Registration  # noqa: E402
from app.services.normalize_keys import normalize_registration_no  # noqa: E402
from app.services.source_contract import upsert_registration_with_contract  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    return v


def _reg(v: str | None) -> str | None:
    return normalize_registration_no(v)


def _is_blank(v: str | None) -> bool:
    return not bool((v or "").strip())


@dataclass
class Sample:
    items: list[dict[str, Any]]
    count: int


def _add_change_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    change_type: str,
    changed_fields: dict[str, dict[str, Any]],
    before_json: dict[str, Any] | None,
    after_json: dict[str, Any] | None,
    after_raw: dict[str, Any] | None,
    product_id: UUID | None = None,
) -> None:
    db.add(
        ChangeLog(
            product_id=product_id,
            entity_type=str(entity_type),
            entity_id=entity_id,
            change_type=str(change_type),
            changed_fields={k: {"old": _json_safe(v.get("old")), "new": _json_safe(v.get("new"))} for k, v in changed_fields.items()},
            before_json=before_json,
            after_json=after_json,
            before_raw=None,
            after_raw=after_raw,
            source_run_id=None,
        )
    )


def _build_registration_norm_map(db: Session) -> tuple[dict[str, UUID], dict[str, list[UUID]]]:
    """Return (unique_map, collisions) where collisions holds normalized keys with >1 registrations."""
    key_to_ids: dict[str, list[UUID]] = defaultdict(list)
    for r in db.scalars(select(Registration)).all():
        k = _reg(getattr(r, "registration_no", None))
        if not k:
            continue
        key_to_ids[k].append(r.id)
    unique: dict[str, UUID] = {}
    collisions: dict[str, list[UUID]] = {}
    for k, ids in key_to_ids.items():
        if len(ids) == 1:
            unique[k] = ids[0]
        else:
            collisions[k] = ids
    return unique, collisions


def _sample_list(rows: list[dict[str, Any]], limit: int) -> Sample:
    return Sample(items=rows[:limit], count=len(rows))


def dry_run(db: Session, *, sample_limit: int = 20) -> dict[str, Any]:
    reg_map, reg_collisions = _build_registration_norm_map(db)

    # a) products 中 reg_no 非空但无法匹配 registrations 的数量与样例
    missing_products: list[dict[str, Any]] = []
    for p in db.scalars(select(Product).where(Product.reg_no.is_not(None))).all():
        raw = str(p.reg_no or "").strip()
        if not raw:
            continue
        k = _reg(raw)
        if not k:
            continue
        if k not in reg_map and k not in reg_collisions:
            missing_products.append(
                {
                    "product_id": str(p.id),
                    "udi_di": p.udi_di,
                    "name": p.name,
                    "reg_no": p.reg_no,
                    "reg_no_norm": k,
                    "registration_id": (str(p.registration_id) if p.registration_id else None),
                }
            )

    # b) products.registration_id 为空但 reg_no 可匹配的数量
    can_backfill_products: list[dict[str, Any]] = []
    for p in db.scalars(select(Product).where(Product.registration_id.is_(None), Product.reg_no.is_not(None))).all():
        raw = str(p.reg_no or "").strip()
        if not raw:
            continue
        k = _reg(raw)
        if not k:
            continue
        rid = reg_map.get(k)
        if rid:
            can_backfill_products.append(
                {
                    "product_id": str(p.id),
                    "udi_di": p.udi_di,
                    "name": p.name,
                    "reg_no": p.reg_no,
                    "reg_no_norm": k,
                    "would_set_registration_id": str(rid),
                }
            )

    # c) product_variants.registry_no 可匹配 registrations 的数量
    match_variants_unique = 0
    match_variants_ambiguous = 0
    sample_variants: list[dict[str, Any]] = []
    for pv in db.scalars(select(ProductVariant).where(ProductVariant.registry_no.is_not(None))).all():
        raw = str(pv.registry_no or "").strip()
        if not raw:
            continue
        k = _reg(raw)
        if not k:
            continue
        if k in reg_map:
            match_variants_unique += 1
            if len(sample_variants) < sample_limit:
                sample_variants.append(
                    {"variant_id": str(pv.id), "di": pv.di, "registry_no": pv.registry_no, "registry_no_norm": k}
                )
        elif k in reg_collisions:
            match_variants_ambiguous += 1

    # d) registry_no 与 products.reg_no 不一致的异常样例 TOP 50
    mismatches: list[dict[str, Any]] = []
    pv_rows = db.scalars(
        select(ProductVariant)
        .where(ProductVariant.product_id.is_not(None))
        .order_by(ProductVariant.updated_at.desc())
    ).all()
    # Fetch products into a dict for quick lookup.
    pids = list({pv.product_id for pv in pv_rows if pv.product_id is not None})
    prod_by_id: dict[UUID, Product] = {}
    if pids:
        for p in db.scalars(select(Product).where(Product.id.in_(pids))).all():
            prod_by_id[p.id] = p
    for pv in pv_rows:
        p = prod_by_id.get(pv.product_id) if pv.product_id else None
        if p is None:
            continue
        k_v = _reg(pv.registry_no)
        k_p = _reg(p.reg_no)
        if not k_v or not k_p:
            continue
        if k_v != k_p:
            mismatches.append(
                {
                    "variant_id": str(pv.id),
                    "di": pv.di,
                    "variant_registry_no": pv.registry_no,
                    "variant_registry_no_norm": k_v,
                    "product_id": str(p.id),
                    "product_reg_no": p.reg_no,
                    "product_reg_no_norm": k_p,
                    "product_udi_di": p.udi_di,
                    "product_name": p.name,
                }
            )
            if len(mismatches) >= 50:
                break

    return {
        "mode": "dry-run",
        "generated_at": _utc_now_iso(),
        "registrations_norm_collisions": {
            "count": len(reg_collisions),
            "sample": [
                {"registration_no_norm": k, "registration_ids": [str(x) for x in ids]}
                for k, ids in list(reg_collisions.items())[: min(20, len(reg_collisions))]
            ],
        },
        "a_products_reg_no_nonempty_but_unmatched": {
            "count": len(missing_products),
            "sample": missing_products[:sample_limit],
        },
        "b_products_registration_id_null_but_reg_no_matchable": {
            "count": len(can_backfill_products),
            "sample": can_backfill_products[:sample_limit],
        },
        "c_variants_registry_no_matchable": {
            "count_unique": match_variants_unique,
            "count_ambiguous": match_variants_ambiguous,
            "sample": sample_variants,
        },
        "d_variant_registry_no_vs_product_reg_no_mismatches_top50": {
            "count": len(mismatches),
            "sample": mismatches,
        },
    }


def execute(db: Session, *, batch_size: int = 1000, sample_limit: int = 20) -> dict[str, Any]:
    reg_map, reg_collisions = _build_registration_norm_map(db)

    updated_products = 0
    updated_variants = 0
    created_registrations = 0
    backfilled_product_registration_id = 0
    ensured_product_registration_id_from_variant = 0
    skipped_ambiguous_registration = 0

    # Helper: resolve normalized key to a single registration_id, else None.
    def _resolve_registration_id(k: str) -> UUID | None:
        nonlocal skipped_ambiguous_registration
        if k in reg_collisions:
            skipped_ambiguous_registration += 1
            return None
        return reg_map.get(k)

    # Iterate products; normalize reg_no, create registration if missing, backfill registration_id.
    products = db.scalars(select(Product).where(Product.reg_no.is_not(None))).all()
    for i, p in enumerate(products, start=1):
        raw_reg = str(p.reg_no or "").strip()
        if _is_blank(raw_reg):
            continue
        norm_reg = _reg(raw_reg)
        if not norm_reg:
            continue

        changed_fields: dict[str, dict[str, Any]] = {}
        before_json = {"reg_no": p.reg_no, "registration_id": (str(p.registration_id) if p.registration_id else None)}
        after_json = dict(before_json)

        # a) normalize products.reg_no
        if p.reg_no != norm_reg:
            changed_fields["reg_no"] = {"old": p.reg_no, "new": norm_reg}
            p.reg_no = norm_reg
            after_json["reg_no"] = norm_reg

        # b) ensure registration exists for this normalized reg_no (products-driven only)
        rid = _resolve_registration_id(norm_reg)
        if rid is None and norm_reg not in reg_collisions and norm_reg not in reg_map:
            try:
                reg_result = upsert_registration_with_contract(
                    db,
                    registration_no=norm_reg,
                    incoming_fields={},
                    source="BACKFILL_REGISTRATION_ANCHOR",
                    source_run_id=None,
                    evidence_grade="B",
                    source_priority=500,
                    observed_at=datetime.now(timezone.utc),
                    raw_source_record_id=None,
                    raw_payload={
                        "backfill": "registration_anchor",
                        "product_id": str(p.id),
                        "udi_di": p.udi_di,
                        "ts": _utc_now_iso(),
                    },
                    write_change_log=True,
                )
            except Exception:
                db.rollback()
                continue
            reg_map[norm_reg] = reg_result.registration_id
            rid = reg_result.registration_id
            if reg_result.created:
                created_registrations += 1

        # c) backfill products.registration_id
        if p.registration_id is None and rid is not None:
            changed_fields["registration_id"] = {"old": None, "new": str(rid)}
            p.registration_id = rid
            after_json["registration_id"] = str(rid)
            backfilled_product_registration_id += 1

        if changed_fields:
            db.add(p)
            _add_change_log(
                db,
                entity_type="product",
                entity_id=p.id,
                change_type="update",
                changed_fields=changed_fields,
                before_json=before_json,
                after_json=after_json,
                after_raw={"backfill": "registration_anchor", "ts": _utc_now_iso()},
                product_id=p.id,
            )
            updated_products += 1

        if i % max(1, batch_size) == 0:
            db.commit()

    db.commit()

    # d) normalize product_variants.registry_no
    variants = db.scalars(select(ProductVariant).where(ProductVariant.registry_no.is_not(None))).all()
    for i, pv in enumerate(variants, start=1):
        raw = str(pv.registry_no or "").strip()
        if _is_blank(raw):
            continue
        norm = _reg(raw)
        if not norm:
            continue
        if pv.registry_no == norm:
            continue

        before_json = {"registry_no": pv.registry_no, "product_id": (str(pv.product_id) if pv.product_id else None)}
        pv.registry_no = norm
        after_json = {"registry_no": norm, "product_id": before_json["product_id"]}
        db.add(pv)
        _add_change_log(
            db,
            entity_type="product_variant",
            entity_id=pv.id,
            change_type="update",
            changed_fields={"registry_no": {"old": before_json["registry_no"], "new": norm}},
            before_json=before_json,
            after_json=after_json,
            after_raw={"backfill": "registration_anchor", "ts": _utc_now_iso()},
            product_id=(pv.product_id if pv.product_id else None),
        )
        updated_variants += 1

        if i % max(1, batch_size) == 0:
            db.commit()
    db.commit()

    # e) for variants with product_id, ensure product.registration_id exists (best-effort).
    pv_rows = db.scalars(select(ProductVariant).where(ProductVariant.product_id.is_not(None))).all()
    pids = list({pv.product_id for pv in pv_rows if pv.product_id is not None})
    prod_by_id: dict[UUID, Product] = {}
    if pids:
        for p in db.scalars(select(Product).where(Product.id.in_(pids))).all():
            prod_by_id[p.id] = p

    for i, pv in enumerate(pv_rows, start=1):
        p = prod_by_id.get(pv.product_id) if pv.product_id else None
        if p is None:
            continue
        if p.registration_id is not None:
            continue

        # Prefer product.reg_no; fallback to variant.registry_no.
        k = _reg(p.reg_no) or _reg(pv.registry_no)
        if not k:
            continue
        rid = _resolve_registration_id(k)
        if rid is None:
            continue
        before_json = {"registration_id": None, "reg_no": p.reg_no}
        p.registration_id = rid
        after_json = {"registration_id": str(rid), "reg_no": p.reg_no}
        db.add(p)
        _add_change_log(
            db,
            entity_type="product",
            entity_id=p.id,
            change_type="update",
            changed_fields={"registration_id": {"old": None, "new": str(rid)}},
            before_json=before_json,
            after_json=after_json,
            after_raw={"backfill": "registration_anchor_from_variant", "ts": _utc_now_iso(), "variant_id": str(pv.id)},
            product_id=p.id,
        )
        ensured_product_registration_id_from_variant += 1

        if i % max(1, batch_size) == 0:
            db.commit()
    db.commit()

    # Re-run dry-run slices for post-execute visibility (small sample only).
    post = dry_run(db, sample_limit=sample_limit)

    return {
        "mode": "execute",
        "finished_at": _utc_now_iso(),
        "stats": {
            "updated_products": updated_products,
            "updated_variants": updated_variants,
            "created_registrations": created_registrations,
            "backfilled_product_registration_id": backfilled_product_registration_id,
            "ensured_product_registration_id_from_variant": ensured_product_registration_id_from_variant,
            "skipped_ambiguous_registration_norm_key": skipped_ambiguous_registration,
        },
        "post_check": post,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backfill registration anchor (normalize reg_no and link registration_id).")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview changes and output diagnostics (default).")
    mode.add_argument("--execute", action="store_true", help="Apply changes (idempotent).")
    p.add_argument("--batch-size", type=int, default=1000, help="Commit every N rows (execute mode).")
    p.add_argument("--sample-limit", type=int, default=20, help="Sample size for dry-run output.")
    return p


def main() -> None:
    args = build_parser().parse_args()
    do_execute = bool(args.execute)
    db = SessionLocal()
    try:
        if do_execute:
            out = execute(db, batch_size=int(args.batch_size), sample_limit=int(args.sample_limit))
        else:
            out = dry_run(db, sample_limit=int(args.sample_limit))
        print(json.dumps(out, ensure_ascii=True, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
