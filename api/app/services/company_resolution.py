from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import ChangeLog, Company, CompanyAlias, Product


_DEFAULT_SUFFIXES = [
    "有限责任公司",
    "股份有限公司",
    "有限公司",
    "集团有限公司",
    "集团",
    "股份",
    "公司",
    "科技有限公司",
    "科技",
    "医疗器械有限公司",
    "医疗器械",
    "医疗",
    "器械",
    "生物科技有限公司",
    "生物科技",
    "生物",
]

_COMPANY_RAW_KEYS = (
    "company_name",
    "manufacturer",
    "注册人名称",
    "生产企业名称",
    "ylqxzcrbarmc",
)


@dataclass
class CompanyAliasSeed:
    remove_suffixes: list[str]
    replacements: dict[str, str]


def load_company_alias_seed(path: str | Path) -> CompanyAliasSeed:
    fp = Path(path)
    data = json.loads(fp.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("company_alias_seed.json must be an object")
    remove_suffixes = data.get("remove_suffixes")
    if not isinstance(remove_suffixes, list):
        remove_suffixes = []
    remove_suffixes = [str(x) for x in remove_suffixes if str(x).strip()]
    replacements = data.get("replacements")
    if not isinstance(replacements, dict):
        replacements = {}
    repl: dict[str, str] = {}
    for k, v in replacements.items():
        ks = str(k).strip()
        vs = str(v).strip()
        if ks and vs:
            repl[ks] = vs
    return CompanyAliasSeed(remove_suffixes=remove_suffixes, replacements=repl)


def normalize_company_name(name: str | None, *, seed: CompanyAliasSeed | None = None) -> str | None:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None

    s = unicodedata.normalize("NFKC", s)
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)

    # Strip surrounding brackets/punct.
    s = s.strip("()[]{}<>，,。.;；:：/\\|·")

    # Apply seed replacements early (after basic normalization).
    if seed and seed.replacements:
        s = seed.replacements.get(s, s)

    # Iteratively strip known suffixes (seed + default) only when at the end.
    suffixes = list(dict.fromkeys((seed.remove_suffixes if seed else []) + _DEFAULT_SUFFIXES))
    suffixes = sorted(suffixes, key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            if suf and s.endswith(suf) and len(s) > len(suf):
                s = s[: -len(suf)]
                changed = True
                break
        if changed:
            s = s.strip("()[]{}<>，,。.;；:：/\\|·")

    # Final cleanup: keep Chinese chars, digits, ASCII letters.
    out = []
    for ch in s:
        o = ord(ch)
        if "0" <= ch <= "9":
            out.append(ch)
        elif "A" <= ch.upper() <= "Z":
            out.append(ch.upper())
        elif 0x4E00 <= o <= 0x9FFF:
            out.append(ch)
        # else drop
    result = "".join(out)
    return result or None


def extract_company_raw_from_product(p: Product) -> str | None:
    # Prefer explicit company link.
    try:
        if getattr(p, "company", None) is not None and getattr(p.company, "name", None):
            return str(p.company.name)
    except Exception:
        pass

    for payload in (getattr(p, "raw_json", None), getattr(p, "raw", None)):
        if isinstance(payload, dict):
            for k in _COMPANY_RAW_KEYS:
                v = payload.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
    return None


def upsert_company_alias(
    db: Session,
    *,
    alias_name: str,
    company_id: UUID,
    confidence: float = 0.8,
    source: str = "manual",
) -> CompanyAlias:
    stmt = insert(CompanyAlias).values(
        alias_name=str(alias_name),
        company_id=company_id,
        confidence=float(confidence),
        source=str(source),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[CompanyAlias.alias_name],
        set_={
            "company_id": stmt.excluded.company_id,
            "confidence": stmt.excluded.confidence,
            "source": stmt.excluded.source,
            "updated_at": func.now(),
        },
    ).returning(CompanyAlias)
    try:
        row = db.execute(stmt).scalar_one()
        return row
    except Exception:
        db.rollback()
        alias = db.scalar(select(CompanyAlias).where(CompanyAlias.alias_name == str(alias_name)))
        if alias is None:
            alias = CompanyAlias(alias_name=str(alias_name), company_id=company_id, confidence=float(confidence), source=str(source))
            db.add(alias)
            db.flush()
        else:
            alias.company_id = company_id
            alias.confidence = float(confidence)
            alias.source = str(source)
            db.add(alias)
            db.flush()
        return alias


def backfill_products_for_alias(*, alias_name: str, company_id: UUID, batch_size: int = 500) -> dict[str, Any]:
    """Best-effort rebind for products whose normalized company raw matches alias_name."""
    db = SessionLocal()
    try:
        updated = 0
        scanned = 0
        q = select(Product).order_by(Product.updated_at.desc()).execution_options(yield_per=1000)
        for p in db.execute(q).scalars():
            scanned += 1
            raw_name = extract_company_raw_from_product(p)
            norm = normalize_company_name(raw_name)
            if not norm or norm != alias_name:
                continue
            if p.company_id == company_id:
                continue
            before_json = {"company_id": (str(p.company_id) if p.company_id else None)}
            p.company_id = company_id
            after_json = {"company_id": str(company_id)}
            db.add(p)
            db.add(
                ChangeLog(
                    product_id=p.id,
                    entity_type="product",
                    entity_id=p.id,
                    change_type="update",
                    changed_fields={"company_id": {"old": before_json["company_id"], "new": after_json["company_id"]}},
                    before_json=before_json,
                    after_json=after_json,
                    after_raw={"backfill": "company_alias_rebind", "alias_name": alias_name},
                    source_run_id=None,
                )
            )
            updated += 1
            if updated % max(1, batch_size) == 0:
                db.commit()
        db.commit()
        return {"ok": True, "alias_name": alias_name, "company_id": str(company_id), "scanned": scanned, "updated": updated}
    finally:
        db.close()
