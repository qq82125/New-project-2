from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AdminConfig, MethodologyMaster, Product, ProductMethodologyMap
from app.repositories.radar import get_admin_config


DEFAULT_ENABLED = True
CFG_ENABLED_KEY = "ontology_v1_methodology_map_enabled"
CFG_RULES_KEY = "ontology_v1_methodology_map_rules"


# Default mapping rules: match tokens from ivd_subtypes/category to methodology codes.
# Admin can override/extend via admin_configs[CFG_RULES_KEY] (JSON object).
DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "PCR": {"tokens": ["pcr", "核酸扩增", "扩增"], "confidence": 0.9},
    "QPCR": {"tokens": ["qpcr", "q pcr", "实时荧光pcr", "实时定量pcr"], "confidence": 0.9},
    "DPCR": {"tokens": ["dpcr", "数字pcr"], "confidence": 0.9},
    "NGS": {"tokens": ["ngs", "二代测序", "高通量测序"], "confidence": 0.85},
    "MNGS": {"tokens": ["mngs", "宏基因组", "宏基因组测序"], "confidence": 0.85},
    "CLIA": {"tokens": ["clia", "化学发光", "发光"], "confidence": 0.8},
    "ECL": {"tokens": ["电化学发光", "ecl"], "confidence": 0.8},
    "ELISA": {"tokens": ["elisa", "酶联免疫"], "confidence": 0.8},
    "ICT": {"tokens": ["免疫层析", "胶体金", "金标", "层析"], "confidence": 0.75},
    "POCT": {"tokens": ["poct", "床旁", "即时检测", "快速检测"], "confidence": 0.7},
    "FLOW": {"tokens": ["流式", "流式细胞"], "confidence": 0.75},
    "BIOCHEM": {"tokens": ["生化", "临床生化"], "confidence": 0.7},
    "MS": {"tokens": ["质谱", "lc-ms", "lcms", "ms"], "confidence": 0.75},
}


def _norm_token(s: str) -> str:
    return str(s or "").strip().lower().replace("（", "(").replace("）", ")")


def _load_rules(db: Session) -> dict[str, dict[str, Any]]:
    cfg = get_admin_config(db, CFG_RULES_KEY)
    if cfg and isinstance(cfg.config_value, dict):
        # Expect shape: { "PCR": {"tokens":[...], "confidence":0.9}, ... }
        return {**DEFAULT_RULES, **cfg.config_value}
    return dict(DEFAULT_RULES)


def _is_enabled(db: Session) -> bool:
    cfg = get_admin_config(db, CFG_ENABLED_KEY)
    if cfg and isinstance(cfg.config_value, dict):
        v = cfg.config_value.get("enabled")
        if v in {True, False}:
            return bool(v)
    return bool(DEFAULT_ENABLED)


@dataclass
class MapProductsResult:
    ok: bool
    dry_run: bool
    total_ivd_products: int
    scanned_products: int
    matched_products: int
    coverage_ratio: float
    inserted_rows: int
    skipped_existing: int
    by_code: dict[str, int]
    disabled: bool = False


def map_products_methodologies_v1(
    db: Session,
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> MapProductsResult:
    if not _is_enabled(db):
        return MapProductsResult(
            ok=True,
            dry_run=bool(dry_run),
            total_ivd_products=0,
            scanned_products=0,
            matched_products=0,
            coverage_ratio=0.0,
            inserted_rows=0,
            skipped_existing=0,
            by_code={},
            disabled=True,
        )

    rules = _load_rules(db)

    # Build code->(id, aliases) index from methodology_master.
    meth_rows = db.scalars(select(MethodologyMaster).where(MethodologyMaster.is_active.is_(True))).all()
    code_to_id: dict[str, UUID] = {}
    token_to_code: dict[str, str] = {}
    for m in meth_rows:
        code = str(m.code or "").strip().upper()
        if not code:
            continue
        code_to_id[code] = m.id
        token_to_code[_norm_token(code)] = code
        if m.aliases:
            for a in m.aliases:
                t = _norm_token(a)
                if t:
                    token_to_code[t] = code

    # Merge rule tokens into token_to_code.
    for code, cfg in rules.items():
        c = str(code or "").strip().upper()
        tokens = cfg.get("tokens") if isinstance(cfg, dict) else None
        if not c or not isinstance(tokens, list):
            continue
        for t in tokens:
            tt = _norm_token(str(t))
            if tt:
                token_to_code[tt] = c

    total_ivd = int(db.scalar(select(func.count(Product.id)).where(Product.is_ivd.is_(True))) or 0)
    q = select(Product).where(Product.is_ivd.is_(True))
    if limit is not None:
        q = q.limit(int(limit))
    products = db.scalars(q).all()

    scanned = len(products)
    matched_products = 0
    inserted_rows = 0
    skipped_existing = 0
    by_code: dict[str, int] = {}

    for p in products:
        tokens: list[str] = []
        if p.ivd_subtypes:
            tokens.extend([_norm_token(x) for x in (p.ivd_subtypes or []) if _norm_token(x)])
        if p.category:
            tokens.append(_norm_token(p.category))

        matched: list[tuple[str, float, str]] = []  # (code, confidence, evidence_text)
        seen_codes: set[str] = set()
        for t in tokens:
            code = token_to_code.get(t)
            if not code:
                continue
            code_u = str(code).strip().upper()
            if code_u in seen_codes:
                continue
            seen_codes.add(code_u)
            cfg = rules.get(code_u, {})
            conf = float(cfg.get("confidence", 0.8) if isinstance(cfg, dict) else 0.8)
            evidence = f"token:{t}"
            matched.append((code_u, conf, evidence))

        # If nothing matched, try very coarse category inference.
        if not matched and p.category:
            cat = _norm_token(p.category)
            coarse = None
            if "发光" in cat:
                coarse = ("CLIA", 0.55, f"category:{cat}")
            elif "免疫" in cat:
                coarse = ("IMMUNO", 0.55, f"category:{cat}")
            elif "生化" in cat:
                coarse = ("BIOCHEM", 0.55, f"category:{cat}")
            if coarse:
                matched.append(coarse)

        # Filter to known methodology codes (must exist in methodology_master).
        final = [(c, conf, ev) for (c, conf, ev) in matched if c in code_to_id]
        if not final:
            continue
        matched_products += 1

        for code, conf, evidence in final:
            by_code[code] = int(by_code.get(code, 0) or 0) + 1
            if dry_run:
                continue
            stmt = insert(ProductMethodologyMap).values(
                product_id=p.id,
                methodology_id=code_to_id[code],
                evidence_raw_document_id=None,
                evidence_text=evidence,
                confidence=conf,
            ).on_conflict_do_nothing(
                index_elements=[ProductMethodologyMap.product_id, ProductMethodologyMap.methodology_id]
            )
            res = db.execute(stmt)
            try:
                if int(res.rowcount or 0) > 0:
                    inserted_rows += 1
                else:
                    skipped_existing += 1
            except Exception:
                pass

    if not dry_run:
        db.commit()

    denom = float(total_ivd if limit is None else max(1, scanned))
    coverage_ratio = float(matched_products / denom) if denom else 0.0

    return MapProductsResult(
        ok=True,
        dry_run=bool(dry_run),
        total_ivd_products=total_ivd,
        scanned_products=scanned,
        matched_products=matched_products,
        coverage_ratio=coverage_ratio,
        inserted_rows=inserted_rows,
        skipped_existing=skipped_existing,
        by_code=by_code,
    )
