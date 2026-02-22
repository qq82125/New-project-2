from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
import re
import unicodedata

from sqlalchemy import select, text, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Product, ProductVariant, Registration, UdiQuarantineEvent
from app.ivd.classifier import DEFAULT_VERSION as IVD_CLASSIFIER_VERSION, classify
from app.sources.nmpa_udi.mapper import map_to_variant
from app.services.normalize_keys import normalize_registration_no
from app.services.source_contract import write_udi_contract_record


@dataclass
class VariantUpsertResult:
    total: int
    skipped: int
    upserted: int
    ivd_true: int
    ivd_false: int
    linked_products: int
    reg_no_backfilled: int
    registration_linked: int
    contract_raw_written: int
    contract_map_written: int
    contract_pending_written: int
    contract_failed: int
    notes: dict[str, Any]


def _resolve_registration_by_no(
    db: Session,
    registry_no: str | None,
    *,
    exact_cache: dict[str, Registration | None],
    norm_cache: dict[str, Registration | None],
) -> Registration | None:
    raw = str(registry_no or "").strip()
    if not raw:
        return None
    if raw in exact_cache:
        return exact_cache[raw]
    reg = db.scalar(select(Registration).where(Registration.registration_no == raw))
    exact_cache[raw] = reg
    if reg is not None:
        return reg

    norm = normalize_registration_no(raw)
    if not norm:
        return None
    if norm in norm_cache:
        return norm_cache[norm]
    rid = db.execute(
        text(
            """
            SELECT id
            FROM registrations
            WHERE regexp_replace(upper(coalesce(registration_no, '')), '[^0-9A-Z一-龥]+', '', 'g') = :n
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"n": norm},
    ).scalar_one_or_none()
    if rid is None:
        norm_cache[norm] = None
        return None
    try:
        reg = db.get(Registration, UUID(str(rid)))
    except Exception:
        reg = None
    norm_cache[norm] = reg
    return reg


def _classification_code_hint(row: dict[str, Any]) -> str:
    for key in ('classification_code', 'class_code', 'flbm', 'cplb', '类别', '管理类别', 'class', 'class_name'):
        v = row.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ''


def upsert_product_variants(
    db: Session,
    *,
    rows: list[dict[str, Any]],
    raw_document_id: UUID | None = None,
    source_run_id: int | None = None,
    dry_run: bool = False,
) -> VariantUpsertResult:
    total = 0
    skipped = 0
    upserted = 0
    ivd_true = 0
    ivd_false = 0
    linked_products = 0
    reg_no_backfilled = 0
    registration_linked = 0
    contract_raw_written = 0
    contract_map_written = 0
    contract_pending_written = 0
    contract_failed = 0
    exact_cache: dict[str, Registration | None] = {}
    norm_cache: dict[str, Registration | None] = {}

    # Cache products by DI to avoid N queries.
    di_list = [str(r.get('udi_di') or r.get('di') or '').strip() for r in rows]
    di_list = [x for x in di_list if x]
    prod_by_di: dict[str, Product] = {}
    if di_list:
        for p in db.scalars(select(Product).where(Product.udi_di.in_(di_list), Product.is_ivd.is_(True))).all():
            prod_by_di[str(p.udi_di)] = p

    for raw in rows:
        total += 1
        # Source Contract shadow write (non-blocking): raw -> parse/normalize -> udi map|pending queue.
        try:
            contract_result = write_udi_contract_record(
                db,
                row=raw,
                source='NMPA_UDI',
                source_run_id=source_run_id,
                source_url=None,
                evidence_grade='A',
                confidence=0.80,
            )
            if contract_result.raw_record_id is not None:
                contract_raw_written += 1
            if contract_result.map_written:
                contract_map_written += 1
            if contract_result.pending_written:
                contract_pending_written += 1
            if contract_result.error:
                contract_failed += 1
        except Exception:
            contract_failed += 1

        mapped = map_to_variant(raw)
        di = (mapped.get('di') or '').strip()
        if not di:
            skipped += 1
            continue

        bound = prod_by_di.get(di)
        if bound is not None:
            linked_products += 1
            is_ivd = True
            category = bound.ivd_category
            product_id = bound.id
            registry_no = (str(mapped.get('registry_no') or '').strip() or None)
            if registry_no and not str(getattr(bound, 'reg_no', '') or '').strip():
                bound.reg_no = registry_no
                db.add(bound)
                reg_no_backfilled += 1
            if not getattr(bound, 'registration_id', None):
                candidate_no = (str(getattr(bound, 'reg_no', '') or '').strip() or registry_no)
                reg = _resolve_registration_by_no(
                    db,
                    candidate_no,
                    exact_cache=exact_cache,
                    norm_cache=norm_cache,
                )
                if reg is not None:
                    bound.registration_id = reg.id
                    # Canonicalize to registrations.registration_no once resolved.
                    if not str(getattr(bound, 'reg_no', '') or '').strip():
                        bound.reg_no = reg.registration_no
                        reg_no_backfilled += 1
                    db.add(bound)
                    registration_linked += 1
            # variants.ivd_version is VARCHAR; store the facade version string for consistency.
            ivd_version = IVD_CLASSIFIER_VERSION
        else:
            decision = classify(
                {'name': mapped.get('product_name') or '', 'classification_code': _classification_code_hint(raw)},
                version=IVD_CLASSIFIER_VERSION,
            )
            is_ivd = bool(decision.get('is_ivd'))
            category = decision.get('ivd_category')
            product_id = None
            ivd_version = str(decision.get('version') or IVD_CLASSIFIER_VERSION)

        if is_ivd:
            ivd_true += 1
        else:
            ivd_false += 1

        if dry_run:
            upserted += 1
            continue

        stmt = insert(ProductVariant).values(
            di=di,
            registry_no=mapped.get('registry_no') or None,
            product_id=product_id,
            product_name=mapped.get('product_name') or None,
            model_spec=mapped.get('model_spec') or None,
            packaging=mapped.get('packaging') or None,
            manufacturer=mapped.get('manufacturer') or None,
            is_ivd=bool(is_ivd),
            ivd_category=(str(category) if category is not None else None),
            ivd_version=str(ivd_version),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProductVariant.di],
            set_={
                'registry_no': stmt.excluded.registry_no,
                'product_id': stmt.excluded.product_id,
                'product_name': stmt.excluded.product_name,
                'model_spec': stmt.excluded.model_spec,
                'packaging': stmt.excluded.packaging,
                'manufacturer': stmt.excluded.manufacturer,
                'is_ivd': stmt.excluded.is_ivd,
                'ivd_category': stmt.excluded.ivd_category,
                'ivd_version': stmt.excluded.ivd_version,
            },
        )
        db.execute(stmt)
        upserted += 1

    if not dry_run:
        db.commit()

    # raw_document_id and source_run_id are kept for traceability via raw_documents.parse_log and source_runs.source_notes.
    notes: dict[str, Any] = {
        'raw_document_id': (str(raw_document_id) if raw_document_id else None),
        'source_run_id': (int(source_run_id) if source_run_id is not None else None),
        'source_contract': {
            'raw_written': contract_raw_written,
            'map_written': contract_map_written,
            'pending_written': contract_pending_written,
            'failed': contract_failed,
        },
    }
    return VariantUpsertResult(
        total=total,
        skipped=skipped,
        upserted=upserted,
        ivd_true=ivd_true,
        ivd_false=ivd_false,
        linked_products=linked_products,
        reg_no_backfilled=reg_no_backfilled,
        registration_linked=registration_linked,
        contract_raw_written=contract_raw_written,
        contract_map_written=contract_map_written,
        contract_pending_written=contract_pending_written,
        contract_failed=contract_failed,
        notes=notes,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UdiVariantsFromIndexReport:
    scanned: int = 0
    bound: int = 0
    unbound: int = 0
    upserted: int = 0
    marked_unbound: int = 0
    duplicate_di_skipped: int = 0
    outlier_regno_skipped: int = 0
    multi_bind_di_skipped: int = 0
    conflicts_recorded: int = 0
    quarantine_event_counts: dict[str, int] | None = None
    quarantine_samples: list[dict[str, Any]] | None = None
    failed: int = 0
    errors: list[dict[str, Any]] | None = None

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "bound": self.bound,
            "unbound": self.unbound,
            "upserted": self.upserted,
            "marked_unbound": self.marked_unbound,
            "duplicate_di_skipped": self.duplicate_di_skipped,
            "outlier_regno_skipped": self.outlier_regno_skipped,
            "multi_bind_di_skipped": self.multi_bind_di_skipped,
            "conflicts_recorded": self.conflicts_recorded,
            "quarantine_event_counts": self.quarantine_event_counts or {},
            "quarantine_samples": self.quarantine_samples or [],
            "failed": self.failed,
            "errors": self.errors or [],
        }


def _compose_model_spec(ggxh: str | None, sku: str | None) -> str | None:
    a = str(ggxh or "").strip()
    b = str(sku or "").strip()
    if a and b:
        return f"{a} / {b}"
    if a:
        return a
    if b:
        return b
    return None


def _record_quarantine_event(
    db: Session,
    *,
    rep: UdiVariantsFromIndexReport,
    dry_run: bool,
    source_run_id: int | None,
    event_type: str,
    reg_no: str | None,
    di: str | None,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    counts = rep.quarantine_event_counts or {}
    counts[event_type] = int(counts.get(event_type, 0) or 0) + 1
    rep.quarantine_event_counts = counts
    samples = rep.quarantine_samples or []
    if len(samples) < 3:
        samples.append(
            {
                "event_type": event_type,
                "reg_no": reg_no,
                "di": di,
                "message": message,
            }
        )
        rep.quarantine_samples = samples

    if dry_run:
        return
    db.add(
        UdiQuarantineEvent(
            source_run_id=(int(source_run_id) if source_run_id is not None else None),
            event_type=event_type,
            reg_no=(str(reg_no).strip() if reg_no else None),
            di=(str(di).strip() if di else None),
            count=1,
            details=(details or None),
            message=message,
        )
    )


def upsert_udi_variants_from_device_index(
    db: Session,
    *,
    source_run_id: int | None = None,
    limit: int | None = None,
    outlier_threshold: int = 100,
    dry_run: bool,
) -> UdiVariantsFromIndexReport:
    """
    Promotion path for UDI device index -> product_variants (registration anchored).

    Rules (contract):
    - Read udi_device_index.di_norm (unique).
    - Must bind via registration_no_norm -> registrations.id; otherwise do NOT write variants.
      Instead mark udi_device_index.status='unbound' (execute only).
    - Upsert product_variants(di unique), filling:
      - registration_id
      - model_spec (ggxh + ' / ' + cphhhbh)
      - manufacturer (ylqxzcrbarmc -> manufacturer_cn)
      - packaging_json (udi_device_index.packing_json, schema: packings[] array)
      - evidence_raw_document_id (raw_document_id)
    """
    rep = UdiVariantsFromIndexReport(errors=[], quarantine_event_counts={}, quarantine_samples=[])

    sql = """
    SELECT
      udi.id AS udi_id,
      udi.di_norm,
      udi.registration_no_norm,
      udi.model_spec,
      udi.sku_code,
      udi.manufacturer_cn,
      udi.packing_json,
      udi.raw_document_id
    FROM udi_device_index udi
    WHERE udi.di_norm IS NOT NULL AND btrim(udi.di_norm) <> ''
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

    # Guard-4A: per batch DI dedupe (idempotency safety).
    # Keep only the latest row per DI (by updated_at desc in SQL order).
    dedup_by_di: dict[str, dict[str, Any]] = {}
    for r in rows:
        di = str(r.get("di_norm") or "").strip()
        if not di:
            continue
        if di in dedup_by_di:
            rep.duplicate_di_skipped += 1
            continue
        dedup_by_di[di] = r
    rows = list(dedup_by_di.values())

    # Guard-4B: identify outlier reg_no and DI multi-bind from index snapshot.
    safety_params: dict[str, Any] = {}
    safety_where = "WHERE di_norm IS NOT NULL AND btrim(di_norm) <> ''"
    if source_run_id is not None:
        safety_where += " AND source_run_id = :source_run_id"
        safety_params["source_run_id"] = int(source_run_id)

    outlier_reg_counts = {
        str(r[0]): int(r[1] or 0)
        for r in db.execute(
            text(
                f"""
                SELECT registration_no_norm, COUNT(1)::bigint AS di_count
                FROM udi_device_index
                {safety_where}
                  AND registration_no_norm IS NOT NULL
                  AND btrim(registration_no_norm) <> ''
                GROUP BY registration_no_norm
                HAVING COUNT(1) > :threshold
                """
            ),
            {**safety_params, "threshold": int(outlier_threshold)},
        ).fetchall()
        if str(r[0] or "").strip()
    }

    multi_bind_di_counts = {
        str(r[0]): int(r[1] or 0)
        for r in db.execute(
            text(
                f"""
                SELECT di_norm, COUNT(DISTINCT registration_no_norm)::bigint AS regno_count
                FROM udi_device_index
                {safety_where}
                  AND registration_no_norm IS NOT NULL
                  AND btrim(registration_no_norm) <> ''
                GROUP BY di_norm
                HAVING COUNT(DISTINCT registration_no_norm) > 1
                """
            ),
            safety_params,
        ).fetchall()
        if str(r[0] or "").strip()
    }

    # Cache registrations by canonical registration_no.
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

    for r in rows:
        rep.scanned += 1
        di = str(r.get("di_norm") or "").strip()
        reg_no = str(r.get("registration_no_norm") or "").strip()
        udi_id = r.get("udi_id")
        raw_document_id = r.get("raw_document_id")

        reg_id = reg_by_no.get(reg_no) if reg_no else None

        if reg_no and reg_no in outlier_reg_counts:
            rep.outlier_regno_skipped += 1
            rep.conflicts_recorded += 1
            try:
                _record_quarantine_event(
                    db,
                    rep=rep,
                    dry_run=dry_run,
                    source_run_id=source_run_id,
                    event_type="UDI_VARIANT_OUTLIER_REGNO",
                    reg_no=reg_no,
                    di=di or None,
                    message=f"reg_no {reg_no} exceeds di_count threshold {int(outlier_threshold)}; variant write quarantined",
                    details={
                        "outlier_threshold": int(outlier_threshold),
                        "di_count": int(outlier_reg_counts.get(reg_no) or 0),
                        "note": "variant write quarantined",
                    },
                )
            except Exception as exc:
                rep.failed += 1
                rep.errors.append({"di": di, "error": f"record_outlier_quarantine_failed: {exc}"})
            continue

        if di and di in multi_bind_di_counts:
            rep.multi_bind_di_skipped += 1
            rep.conflicts_recorded += 1
            try:
                _record_quarantine_event(
                    db,
                    rep=rep,
                    dry_run=dry_run,
                    source_run_id=source_run_id,
                    event_type="UDI_VARIANT_MULTI_BIND_DI",
                    reg_no=reg_no or None,
                    di=di,
                    message=f"di {di} binds multiple registration_no values; variant write quarantined",
                    details={
                        "regno_count": int(multi_bind_di_counts.get(di) or 0),
                        "note": "variant write quarantined",
                    },
                )
            except Exception as exc:
                rep.failed += 1
                rep.errors.append({"di": di, "error": f"record_multi_bind_quarantine_failed: {exc}"})
            continue

        if reg_id is None:
            rep.unbound += 1
            if (not dry_run) and udi_id:
                try:
                    db.execute(
                        text("UPDATE udi_device_index SET status = 'unbound', updated_at = NOW() WHERE id = :id"),
                        {"id": str(udi_id)},
                    )
                    rep.marked_unbound += 1
                except Exception as exc:
                    rep.failed += 1
                    rep.errors.append({"di": di, "error": f"mark_unbound_failed: {exc}"})
            continue

        rep.bound += 1
        if dry_run:
            rep.upserted += 1
            continue

        try:
            model_spec = _compose_model_spec(r.get("model_spec"), r.get("sku_code"))
            manufacturer = (str(r.get("manufacturer_cn") or "").strip() or None)
            packing_json = r.get("packing_json")
            ev_raw_id = str(raw_document_id) if raw_document_id else None

            stmt = insert(ProductVariant).values(
                di=di,
                registry_no=reg_no,
                registration_id=reg_id,
                model_spec=model_spec,
                manufacturer=manufacturer,
                packaging_json=packing_json,
                evidence_raw_document_id=(UUID(ev_raw_id) if ev_raw_id else None),
                updated_at=func.now(),
            )
            existing = db.scalar(select(ProductVariant).where(ProductVariant.di == di).limit(1))
            if existing is not None:
                existing_reg = str(getattr(existing, "registry_no", "") or "").strip()
                if existing_reg and reg_no and existing_reg != reg_no:
                    rep.multi_bind_di_skipped += 1
                    rep.conflicts_recorded += 1
                    _record_quarantine_event(
                        db,
                        rep=rep,
                        dry_run=dry_run,
                        source_run_id=source_run_id,
                        event_type="UDI_VARIANT_MULTI_BIND_DI",
                        reg_no=reg_no,
                        di=di,
                        message=f"existing variant di={di} already linked to reg_no={existing_reg}, new reg_no={reg_no}; quarantined",
                        details={
                            "existing_reg_no": existing_reg,
                            "incoming_reg_no": reg_no,
                            "note": "variant write quarantined",
                        },
                    )
                    continue

            stmt = stmt.on_conflict_do_update(
                index_elements=[ProductVariant.di],
                set_={
                    "registry_no": func.coalesce(stmt.excluded.registry_no, ProductVariant.registry_no),
                    "registration_id": func.coalesce(stmt.excluded.registration_id, ProductVariant.registration_id),
                    "model_spec": func.coalesce(stmt.excluded.model_spec, ProductVariant.model_spec),
                    "manufacturer": func.coalesce(stmt.excluded.manufacturer, ProductVariant.manufacturer),
                    "packaging_json": func.coalesce(stmt.excluded.packaging_json, ProductVariant.packaging_json),
                    "evidence_raw_document_id": func.coalesce(stmt.excluded.evidence_raw_document_id, ProductVariant.evidence_raw_document_id),
                    "updated_at": text("NOW()"),
                },
            )
            db.execute(stmt)
            rep.upserted += 1
        except Exception as exc:
            rep.failed += 1
            rep.errors.append({"di": di, "error": str(exc)})

    if not dry_run:
        db.commit()
    return rep


@dataclass
class UdiReplayRegnoReport:
    source_run_id: int
    registration_nos: list[str]
    scanned: int = 0
    selected_for_write: int = 0
    deleted_variants: int = 0
    deleted_links: int = 0
    upserted: int = 0
    multi_bind_di_skipped: int = 0
    failed: int = 0
    regno_stats: list[dict[str, Any]] | None = None
    errors: list[dict[str, Any]] | None = None

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "source_run_id": int(self.source_run_id),
            "registration_nos": list(self.registration_nos),
            "scanned": int(self.scanned),
            "selected_for_write": int(self.selected_for_write),
            "deleted_variants": int(self.deleted_variants),
            "deleted_links": int(self.deleted_links),
            "upserted": int(self.upserted),
            "multi_bind_di_skipped": int(self.multi_bind_di_skipped),
            "failed": int(self.failed),
            "regno_stats": list(self.regno_stats or []),
            "errors": list(self.errors or []),
        }


def _model_family_key(model_spec: str | None, sku_code: str | None) -> str:
    """
    Type-A replay split rule:
    - Normalize model text (NFKC).
    - Prefer segment before "/" (plate-like patterns).
    - Then trim dimension tail after ×/x/X/* (wire-like patterns).
    - Remove trailing孔位/纯数字规格尾缀.
    """
    base = (model_spec or sku_code or "").strip()
    if not base:
        return "__EMPTY_MODEL__"
    s = unicodedata.normalize("NFKC", base).strip()
    s = re.sub(r"\s+", "", s)
    if "/" in s:
        s = s.split("/", 1)[0].strip()
    if "／" in s:
        s = s.split("／", 1)[0].strip()
    for sep in ("×", "x", "X", "*", "＊"):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    s = re.sub(r"(\\d+(\\.\\d+)?孔)$", "", s)
    s = re.sub(r"(\\d+(\\.\\d+)?)$", "", s)
    s = s.strip()
    return s or "__EMPTY_MODEL__"


def replay_udi_variants_for_regnos(
    db: Session,
    *,
    source_run_id: int,
    registration_nos: list[str],
    outlier_threshold: int = 100,
    dry_run: bool,
) -> UdiReplayRegnoReport:
    reg_nos = sorted({str(x or "").strip() for x in registration_nos if str(x or "").strip()})
    rep = UdiReplayRegnoReport(
        source_run_id=int(source_run_id),
        registration_nos=reg_nos,
        regno_stats=[],
        errors=[],
    )
    if not reg_nos:
        return rep

    rows = db.execute(
        text(
            """
            SELECT
              udi.di_norm,
              udi.registration_no_norm,
              udi.model_spec,
              udi.sku_code,
              udi.manufacturer_cn,
              udi.packing_json,
              udi.raw_document_id
            FROM udi_device_index udi
            WHERE udi.source_run_id = :srid
              AND udi.registration_no_norm = ANY(:arr)
              AND udi.di_norm IS NOT NULL
              AND btrim(udi.di_norm) <> ''
            ORDER BY udi.registration_no_norm ASC, udi.di_norm ASC
            """
        ),
        {"srid": int(source_run_id), "arr": reg_nos},
    ).mappings().all()

    rep.scanned = len(rows)
    rows_by_reg: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        reg = str(r.get("registration_no_norm") or "").strip()
        if not reg:
            continue
        rows_by_reg.setdefault(reg, []).append(dict(r))

    # Cache registrations for anchor checks.
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

    selected_rows: list[dict[str, Any]] = []
    all_di_by_reg: dict[str, list[str]] = {}
    for reg_no in reg_nos:
        src_rows = rows_by_reg.get(reg_no, [])
        all_di = [str(x.get("di_norm") or "").strip() for x in src_rows if str(x.get("di_norm") or "").strip()]
        all_di_by_reg[reg_no] = all_di
        before_cnt = len(all_di)

        family_map: dict[str, dict[str, Any]] = {}
        for x in src_rows:
            fam = _model_family_key(
                str(x.get("model_spec") or "").strip() or None,
                str(x.get("sku_code") or "").strip() or None,
            )
            # deterministic representative: lexicographically smallest DI in family
            if fam not in family_map:
                family_map[fam] = x
                continue
            old_di = str(family_map[fam].get("di_norm") or "").strip()
            new_di = str(x.get("di_norm") or "").strip()
            if new_di and (not old_di or new_di < old_di):
                family_map[fam] = x

        # Apply split rule only when it's an extreme outlier.
        if before_cnt > int(outlier_threshold):
            chosen = sorted(
                family_map.values(),
                key=lambda v: str(v.get("di_norm") or ""),
            )
            strategy = "family_split_dedupe"
        else:
            chosen = src_rows
            strategy = "keep_all"

        after_cnt = len(chosen)
        rep.regno_stats.append(
            {
                "registration_no": reg_no,
                "before_di_count": int(before_cnt),
                "after_di_count": int(after_cnt),
                "family_count": int(len(family_map)),
                "strategy": strategy,
            }
        )
        selected_rows.extend(chosen)

    rep.selected_for_write = len(selected_rows)

    if dry_run:
        return rep

    # Rebuild only targeted regno rows: delete old rows from this run's DI set, then upsert selected.
    for reg_no in reg_nos:
        di_arr = all_di_by_reg.get(reg_no, [])
        if not di_arr:
            continue
        deleted_v = db.execute(
            text(
                """
                DELETE FROM product_variants
                WHERE registry_no = :reg_no
                  AND di = ANY(:di_arr)
                """
            ),
            {"reg_no": reg_no, "di_arr": di_arr},
        ).rowcount
        rep.deleted_variants += int(deleted_v or 0)

        deleted_m = db.execute(
            text(
                """
                DELETE FROM product_udi_map
                WHERE registration_no = :reg_no
                  AND di = ANY(:di_arr)
                """
            ),
            {"reg_no": reg_no, "di_arr": di_arr},
        ).rowcount
        rep.deleted_links += int(deleted_m or 0)

    # Reinsert selected rows with anchor checks and multi-bind guard.
    for r in selected_rows:
        di = str(r.get("di_norm") or "").strip()
        reg_no = str(r.get("registration_no_norm") or "").strip()
        reg_id = reg_by_no.get(reg_no)
        if not di or not reg_no or reg_id is None:
            continue
        try:
            existing = db.scalar(select(ProductVariant).where(ProductVariant.di == di).limit(1))
            if existing is not None:
                existing_reg = str(getattr(existing, "registry_no", "") or "").strip()
                if existing_reg and existing_reg != reg_no:
                    rep.multi_bind_di_skipped += 1
                    continue

            model_spec = _compose_model_spec(r.get("model_spec"), r.get("sku_code"))
            manufacturer = (str(r.get("manufacturer_cn") or "").strip() or None)
            packing_json = r.get("packing_json")
            raw_document_id = r.get("raw_document_id")
            ev_raw_id = str(raw_document_id) if raw_document_id else None

            stmt = insert(ProductVariant).values(
                di=di,
                registry_no=reg_no,
                registration_id=reg_id,
                model_spec=model_spec,
                manufacturer=manufacturer,
                packaging_json=packing_json,
                evidence_raw_document_id=(UUID(ev_raw_id) if ev_raw_id else None),
                updated_at=func.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ProductVariant.di],
                set_={
                    "registry_no": func.coalesce(stmt.excluded.registry_no, ProductVariant.registry_no),
                    "registration_id": func.coalesce(stmt.excluded.registration_id, ProductVariant.registration_id),
                    "model_spec": func.coalesce(stmt.excluded.model_spec, ProductVariant.model_spec),
                    "manufacturer": func.coalesce(stmt.excluded.manufacturer, ProductVariant.manufacturer),
                    "packaging_json": func.coalesce(stmt.excluded.packaging_json, ProductVariant.packaging_json),
                    "evidence_raw_document_id": func.coalesce(stmt.excluded.evidence_raw_document_id, ProductVariant.evidence_raw_document_id),
                    "updated_at": text("NOW()"),
                },
            )
            db.execute(stmt)
            db.execute(
                text(
                    """
                    INSERT INTO product_udi_map(registration_no, di, match_type, confidence, source, created_at, updated_at)
                    VALUES (:reg_no, :di, 'direct', 1.0, 'UDI_REPLAY_REGNO', NOW(), NOW())
                    ON CONFLICT (registration_no, di) DO UPDATE SET
                      updated_at = NOW(),
                      source = EXCLUDED.source
                    """
                ),
                {"reg_no": reg_no, "di": di},
            )
            rep.upserted += 1
        except Exception as exc:
            rep.failed += 1
            rep.errors.append({"reg_no": reg_no, "di": di, "error": str(exc)})

    db.commit()
    return rep
