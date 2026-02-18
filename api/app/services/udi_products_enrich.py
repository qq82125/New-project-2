from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import ChangeLog, Product, Registration


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _is_placeholder_name(v: str | None) -> bool:
    s = str(v or "").strip()
    return (not s) or (s.upper() == "UDI-STUB")


def _truncate(v: str | None, n: int) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    if len(s) <= n:
        return s
    return s[:n]


def _merge_list_unique(items: list[str], *candidates: str | None, max_len: int = 50) -> list[str]:
    seen = {str(x) for x in items if str(x).strip()}
    out = [str(x) for x in items if str(x).strip()]
    for c in candidates:
        s = str(c or "").strip()
        if not s or s in seen:
            continue
        out.append(s)
        seen.add(s)
        if len(out) >= max_len:
            break
    return out


@dataclass
class UdiProductsEnrichReport:
    scanned: int = 0
    reg_bound: int = 0
    product_bound: int = 0
    updated: int = 0
    skipped_no_product: int = 0
    skipped_no_change: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] | None = None

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "reg_bound": self.reg_bound,
            "product_bound": self.product_bound,
            "updated": self.updated,
            "skipped_no_product": self.skipped_no_product,
            "skipped_no_change": self.skipped_no_change,
            "failed": self.failed,
            "errors": self.errors or [],
        }


def enrich_products_from_udi_device_index(
    db: Session,
    *,
    source_run_id: int | None = None,
    limit: int | None = None,
    dry_run: bool,
    description_max_len: int = 2000,
) -> UdiProductsEnrichReport:
    """
    Enrich products using UDI device index, without overriding existing (NMPA) facts.

    Rules:
    - Only process rows that can bind registration_no_norm -> registrations.id.
    - Only update product columns when target field is empty/placeholder.
    - Never override existing values: if different, store under products.raw_json.udi_snapshot / aliases.
    """
    rep = UdiProductsEnrichReport(errors=[])

    sql = """
    SELECT
      udi.di_norm,
      udi.registration_no_norm,
      udi.product_name,
      udi.brand,
      udi.model_spec,
      udi.description,
      udi.category_big,
      udi.product_type,
      udi.class_code,
      udi.raw_document_id,
      udi.source_run_id,
      udi.updated_at
    FROM udi_device_index udi
    WHERE udi.di_norm IS NOT NULL AND btrim(udi.di_norm) <> ''
      AND udi.registration_no_norm IS NOT NULL AND btrim(udi.registration_no_norm) <> ''
    """
    params: dict[str, Any] = {}
    if source_run_id is not None:
        sql += " AND udi.source_run_id = :source_run_id"
        params["source_run_id"] = int(source_run_id)
    sql += " ORDER BY udi.updated_at DESC NULLS LAST"
    if isinstance(limit, int) and limit > 0:
        sql += " LIMIT :lim"
        params["lim"] = int(limit)

    rows = db.execute(text(sql), params).mappings().all()
    rep.scanned = len(rows)

    reg_nos = sorted({str(r.get("registration_no_norm") or "").strip() for r in rows if str(r.get("registration_no_norm") or "").strip()})
    reg_by_no: dict[str, UUID] = {}
    if reg_nos:
        for rid, rno in db.execute(
            text("SELECT id, registration_no FROM registrations WHERE registration_no = ANY(:arr)"),
            {"arr": reg_nos},
        ).fetchall():
            try:
                reg_by_no[str(rno)] = UUID(str(rid))
            except Exception:
                continue

    # Pick one "display product" per registration_id: latest updated IVD product.
    reg_ids = list({str(x) for x in reg_by_no.values()})
    prod_by_reg_id: dict[UUID, Product] = {}
    if reg_ids:
        products = (
            db.scalars(
                select(Product)
                .where(Product.registration_id.in_([UUID(x) for x in reg_ids]), Product.is_ivd.is_(True))
                .order_by(Product.updated_at.desc(), Product.created_at.desc())
            )
            .all()
        )
        for p in products:
            rid = getattr(p, "registration_id", None)
            if rid and rid not in prod_by_reg_id:
                prod_by_reg_id[rid] = p

    for r in rows:
        di = _as_text(r.get("di_norm")) or ""
        reg_no = _as_text(r.get("registration_no_norm")) or ""
        reg_id = reg_by_no.get(reg_no)
        if reg_id is None:
            continue
        rep.reg_bound += 1

        product = prod_by_reg_id.get(reg_id)
        if product is None:
            rep.skipped_no_product += 1
            continue
        rep.product_bound += 1

        udi_name = _as_text(r.get("product_name")) or _as_text(r.get("brand"))
        udi_model = _as_text(r.get("model_spec"))
        udi_desc = _truncate(_as_text(r.get("description")), description_max_len)
        udi_fields = {
            "di_norm": di,
            "registration_no_norm": reg_no,
            "product_name": _as_text(r.get("product_name")),
            "brand": _as_text(r.get("brand")),
            "ggxh": udi_model,
            "qxlb": _as_text(r.get("category_big")),
            "cplb": _as_text(r.get("product_type")),
            "flbm": _as_text(r.get("class_code")),
            "description": udi_desc,
            "raw_document_id": (str(r.get("raw_document_id")) if r.get("raw_document_id") else None),
            "source_run_id": (int(r.get("source_run_id")) if r.get("source_run_id") is not None else None),
            "observed_at": (str(r.get("updated_at")) if r.get("updated_at") is not None else None),
        }

        before_cols = {
            "name": getattr(product, "name", None),
            "model": getattr(product, "model", None),
            "category": getattr(product, "category", None),
            "raw_json": (dict(getattr(product, "raw_json", {}) or {}) if isinstance(getattr(product, "raw_json", None), dict) else {}),
        }
        changed_fields: dict[str, Any] = {}

        # Column enrich: only fill empty / placeholder.
        if udi_name and _is_placeholder_name(str(getattr(product, "name", "") or "")):
            changed_fields["name"] = {"old": getattr(product, "name", None), "new": udi_name}
            if not dry_run:
                product.name = udi_name

        if udi_model and not _as_text(getattr(product, "model", None)):
            changed_fields["model"] = {"old": getattr(product, "model", None), "new": udi_model}
            if not dry_run:
                product.model = udi_model

        # category: best-effort only when empty, prefer qxlb then cplb.
        if not _as_text(getattr(product, "category", None)):
            cat = _as_text(r.get("category_big")) or _as_text(r.get("product_type"))
            if cat:
                changed_fields["category"] = {"old": getattr(product, "category", None), "new": cat}
                if not dry_run:
                    product.category = cat

        # raw_json enrich: always store udi_snapshot; do not overwrite existing description if already present.
        raw = before_cols["raw_json"]
        raw2 = dict(raw)
        raw2["udi_snapshot"] = udi_fields

        sf = raw2.get("search_fields")
        if not isinstance(sf, dict):
            sf = {}
        udi_sf = sf.get("udi")
        if not isinstance(udi_sf, dict):
            udi_sf = {}
        for k in ("qxlb", "cplb", "flbm"):
            v = _as_text(udi_fields.get(k))
            if v:
                udi_sf[k] = v
        sf["udi"] = udi_sf
        raw2["search_fields"] = sf

        # Only set a top-level description if missing (avoid overriding existing NMPA-provided text).
        if udi_desc and not _as_text(raw2.get("description")):
            raw2["description"] = udi_desc

        # Aliases: keep UDI name/model if they differ from current.
        aliases = raw2.get("aliases")
        if not isinstance(aliases, dict):
            aliases = {}
        names = aliases.get("udi_names")
        if not isinstance(names, list):
            names = []
        models = aliases.get("udi_models")
        if not isinstance(models, list):
            models = []
        if udi_name and udi_name != _as_text(getattr(product, "name", None)):
            names = _merge_list_unique([str(x) for x in names if str(x).strip()], udi_name)
        if udi_model and udi_model != _as_text(getattr(product, "model", None)):
            models = _merge_list_unique([str(x) for x in models if str(x).strip()], udi_model)
        aliases["udi_names"] = names
        aliases["udi_models"] = models
        raw2["aliases"] = aliases

        if raw2 != raw:
            changed_fields["raw_json"] = {"old": "(redacted)", "new": "(redacted)"}
            if not dry_run:
                product.raw_json = raw2

        if not changed_fields:
            rep.skipped_no_change += 1
            continue

        if dry_run:
            rep.updated += 1
            continue

        try:
            db.add(product)
            db.flush()
            after_cols = {
                "name": getattr(product, "name", None),
                "model": getattr(product, "model", None),
                "category": getattr(product, "category", None),
                "raw_json": (dict(getattr(product, "raw_json", {}) or {}) if isinstance(getattr(product, "raw_json", None), dict) else {}),
            }
            db.add(
                ChangeLog(
                    product_id=product.id,
                    entity_type="product",
                    entity_id=product.id,
                    change_type="update",
                    changed_fields=changed_fields,
                    before_json=before_cols,
                    after_json=after_cols,
                    before_raw=None,
                    after_raw={
                        "source": "UDI_PRODUCTS_ENRICH",
                        "di_norm": di,
                        "registration_no_norm": reg_no,
                        "raw_document_id": udi_fields.get("raw_document_id"),
                        "source_run_id": udi_fields.get("source_run_id"),
                        "observed_at": udi_fields.get("observed_at"),
                        "udi_snapshot": udi_fields,
                    },
                    source_run_id=(int(r.get("source_run_id")) if r.get("source_run_id") is not None else None),
                )
            )
            rep.updated += 1
        except Exception as exc:
            rep.failed += 1
            rep.errors.append({"di": di, "error": str(exc)})

    if not dry_run:
        db.commit()
    return rep

