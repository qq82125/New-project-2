#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import ChangeLog, Company, CompanyAlias, Product  # noqa: E402
from app.services.company_resolution import (  # noqa: E402
    extract_company_raw_from_product,
    load_company_alias_seed,
    normalize_company_name,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    return v


def _add_product_change_log(db: Session, *, product_id: UUID, old_company_id: UUID | None, new_company_id: UUID) -> None:
    before_json = {"company_id": (str(old_company_id) if old_company_id else None)}
    after_json = {"company_id": str(new_company_id)}
    db.add(
        ChangeLog(
            product_id=product_id,
            entity_type="product",
            entity_id=product_id,
            change_type="update",
            changed_fields={"company_id": {"old": before_json["company_id"], "new": after_json["company_id"]}},
            before_json=before_json,
            after_json=after_json,
            after_raw={"backfill": "company_resolution", "ts": _utc_now_iso()},
            source_run_id=None,
        )
    )


def _add_company_change_log(db: Session, *, company_id: UUID, name: str) -> None:
    db.add(
        ChangeLog(
            product_id=None,
            entity_type="company",
            entity_id=company_id,
            change_type="new",
            changed_fields={"name": {"old": None, "new": name}},
            before_json=None,
            after_json={"name": name},
            after_raw={"backfill": "company_resolution", "ts": _utc_now_iso()},
            source_run_id=None,
        )
    )


def _build_alias_map(db: Session) -> dict[str, UUID]:
    out: dict[str, UUID] = {}
    for a in db.scalars(select(CompanyAlias)).all():
        k = str(getattr(a, "alias_name", "") or "").strip()
        if not k:
            continue
        out[k] = a.company_id
    return out


def _build_company_name_maps(db: Session, *, seed) -> tuple[dict[str, UUID], dict[str, list[UUID]]]:
    """Return (unique_norm_map, collisions) for normalized company names."""
    norm_to_ids: dict[str, list[UUID]] = defaultdict(list)
    for c in db.scalars(select(Company)).all():
        n = normalize_company_name(getattr(c, "name", None), seed=seed)
        if not n:
            continue
        norm_to_ids[n].append(c.id)
    unique: dict[str, UUID] = {}
    collisions: dict[str, list[UUID]] = {}
    for k, ids in norm_to_ids.items():
        if len(ids) == 1:
            unique[k] = ids[0]
        else:
            collisions[k] = ids
    return unique, collisions


def dry_run(db: Session, *, seed_path: Path, sample_limit: int = 20, top_n: int = 30) -> dict[str, Any]:
    seed = load_company_alias_seed(seed_path) if seed_path.exists() else None
    alias_map = _build_alias_map(db)
    company_norm_map, company_norm_collisions = _build_company_name_maps(db, seed=seed)

    total = 0
    has_company_id = 0
    has_raw = 0
    norm_ok = 0

    raw_counter: Counter[str] = Counter()
    norm_counter: Counter[str] = Counter()

    norm_to_raws: dict[str, set[str]] = defaultdict(set)
    norm_to_company_ids: dict[str, set[str]] = defaultdict(set)

    sample_conflicts: list[dict[str, Any]] = []

    q = select(Product).order_by(Product.updated_at.desc()).execution_options(yield_per=1000)
    for p in db.execute(q).scalars():
        total += 1
        if p.company_id is not None:
            has_company_id += 1
        raw = extract_company_raw_from_product(p)
        if raw and str(raw).strip():
            has_raw += 1
            raw_counter[str(raw).strip()] += 1
        norm = normalize_company_name(raw, seed=seed)
        if norm:
            norm_ok += 1
            norm_counter[norm] += 1
            if raw:
                norm_to_raws[norm].add(str(raw).strip())
            if p.company_id is not None:
                norm_to_company_ids[norm].add(str(p.company_id))

    # Conflict examples: same normalized key observed with multiple company_ids or many raw variants.
    for norm, ids in norm_to_company_ids.items():
        raws = norm_to_raws.get(norm) or set()
        if len(ids) > 1 or len(raws) >= 5:
            sample_conflicts.append(
                {
                    "normalized_name": norm,
                    "distinct_company_ids": sorted(list(ids))[:10],
                    "distinct_raw_names_sample": sorted(list(raws))[:10],
                    "companies_norm_collision": (norm in company_norm_collisions),
                    "has_alias_mapping": (norm in alias_map),
                }
            )
        if len(sample_conflicts) >= sample_limit:
            break

    return {
        "mode": "dry-run",
        "generated_at": _utc_now_iso(),
        "seed_path": str(seed_path),
        "coverage": {
            "products_total": total,
            "products_with_company_id": has_company_id,
            "products_with_company_raw": has_raw,
            "products_company_raw_normalizable": norm_ok,
        },
        "top_company_raw": [{"name": k, "count": int(v)} for k, v in raw_counter.most_common(top_n)],
        "top_company_norm": [{"name": k, "count": int(v)} for k, v in norm_counter.most_common(top_n)],
        "company_norm_collisions": {
            "count": len(company_norm_collisions),
            "sample": [
                {"normalized_name": k, "company_ids": [str(x) for x in ids]}
                for k, ids in list(company_norm_collisions.items())[: min(20, len(company_norm_collisions))]
            ],
        },
        "conflict_samples": sample_conflicts,
    }


def execute(db: Session, *, seed_path: Path, batch_size: int = 500, sample_limit: int = 20) -> dict[str, Any]:
    seed = load_company_alias_seed(seed_path) if seed_path.exists() else None
    alias_map = _build_alias_map(db)
    company_norm_map, company_norm_collisions = _build_company_name_maps(db, seed=seed)

    scanned = 0
    created_companies = 0
    updated_products = 0
    skipped_ambiguous_norm = 0
    skipped_blank = 0

    q = select(Product).order_by(Product.updated_at.desc()).execution_options(yield_per=1000)
    for p in db.execute(q).scalars():
        scanned += 1
        raw = extract_company_raw_from_product(p)
        norm = normalize_company_name(raw, seed=seed)
        if not norm:
            skipped_blank += 1
            continue

        # Resolve company_id
        target_company_id: UUID | None = alias_map.get(norm)
        if target_company_id is None:
            if norm in company_norm_collisions:
                skipped_ambiguous_norm += 1
                continue
            target_company_id = company_norm_map.get(norm)

        if target_company_id is None:
            # Create company using normalized name as canonical key.
            c = Company(name=norm, country=None, raw_json={"created_by": "backfill_company_resolution", "ts": _utc_now_iso()}, raw={})
            db.add(c)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                # Re-query; the UNIQUE constraint on companies.name should ensure one row.
                c = db.scalar(select(Company).where(Company.name == norm))
                if c is None:
                    continue
            created_companies += 1
            target_company_id = c.id
            company_norm_map[norm] = c.id
            _add_company_change_log(db, company_id=c.id, name=norm)

        if p.company_id == target_company_id:
            continue

        old = p.company_id
        p.company_id = target_company_id
        db.add(p)
        _add_product_change_log(db, product_id=p.id, old_company_id=old, new_company_id=target_company_id)
        updated_products += 1

        if updated_products % max(1, batch_size) == 0:
            db.commit()

    db.commit()

    post = dry_run(db, seed_path=seed_path, sample_limit=sample_limit)
    return {
        "mode": "execute",
        "finished_at": _utc_now_iso(),
        "seed_path": str(seed_path),
        "stats": {
            "scanned_products": scanned,
            "updated_products": updated_products,
            "created_companies": created_companies,
            "skipped_blank_or_unextractable": skipped_blank,
            "skipped_ambiguous_normalized_name": skipped_ambiguous_norm,
        },
        "post_check": post,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backfill company resolution (normalize -> alias/company -> products.company_id).")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview diagnostics only (default).")
    mode.add_argument("--execute", action="store_true", help="Apply changes (idempotent).")
    p.add_argument("--seed", default=str(REPO_ROOT / "docs" / "company_alias_seed.json"), help="Seed json path.")
    p.add_argument("--batch-size", type=int, default=500, help="Commit every N updated products (execute mode).")
    p.add_argument("--sample-limit", type=int, default=20, help="Sample size for dry-run conflict output.")
    return p


def main() -> None:
    args = build_parser().parse_args()
    seed_path = Path(str(args.seed))
    db = SessionLocal()
    try:
        if bool(args.execute):
            out = execute(db, seed_path=seed_path, batch_size=int(args.batch_size), sample_limit=int(args.sample_limit))
        else:
            out = dry_run(db, seed_path=seed_path, sample_limit=int(args.sample_limit))
        print(json.dumps(out, ensure_ascii=True, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()

