from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChangeLog, Product, ProductUdiMap, ProductVariant, Registration, RawDocument, PendingRecord
from app.services.normalize_keys import normalize_registration_no
from app.services.source_contract import upsert_registration_with_contract


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value if text_value else None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _as_json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    except Exception:
        return None


def _pick_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key not in row:
            continue
        val = row.get(key)
        text_val = _as_text(val)
        if text_val:
            return text_val
    return None


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def _payload_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return sha256(blob).hexdigest()


def _merge_stub(raw_json: dict[str, Any] | None, *, evidence_level: str = "LOW", source_hint: str = "UDI", verified_by_nmpa: bool = False) -> dict[str, Any]:
    base = dict(raw_json or {})
    stub = dict(base.get("_stub") or {}) if isinstance(base.get("_stub"), dict) else {}
    stub.update(
        {
            "evidence_level": evidence_level,
            "source_hint": source_hint,
            "verified_by_nmpa": bool(verified_by_nmpa),
        }
    )
    base["_stub"] = stub
    return base


def _product_stub_name(row: dict[str, Any]) -> str:
    return (
        _pick_text(row, "cpmctymc", "spmc")
        or _pick_text(row, "product_name", "brand", "manufacturer", "manufacturer_cn", "manufacturer_en")
        or "UDI-STUB"
    )


def _product_ivd_category(row: dict[str, Any]) -> str | None:
    return (
        _pick_text(row, "product_type", "cplb", "ivd_category", "category_big")
        or "OTHER"
    )


def _extract_company(row: dict[str, Any]) -> str | None:
    return _pick_text(row, "manufacturer_cn", "manufacturer_en", "manufacturer", "company_name", "manufacturer_name", "spmc")


def _extract_source_run_id(row: dict[str, Any], cli_source_run_id: int | None) -> int | None:
    if cli_source_run_id is not None:
        return cli_source_run_id
    val = _pick_text(row, "source_run_id")
    if not val:
        return None
    return _as_int(val)


def _extract_raw_document_id(row: dict[str, Any], override_raw_document_id: UUID | None) -> UUID | None:
    if override_raw_document_id is not None:
        return override_raw_document_id
    return _as_uuid(_pick_text(row, "raw_document_id"))


def _ensure_raw_document(
    db: Session,
    *,
    row: dict[str, Any],
    source: str,
    source_run_id: int | None,
) -> UUID:
    raw_id = _as_uuid(_pick_text(row, "raw_document_id"))
    if raw_id is not None:
        return raw_id

    payload = row
    payload_hash = _payload_hash(payload)
    run_id = str(source_run_id) if source_run_id is not None else _pick_text(row, "run_id") or source

    existing = db.scalar(
        select(RawDocument).where(
            RawDocument.source == source,
            RawDocument.run_id == run_id,
            RawDocument.sha256 == payload_hash,
        )
    )
    if existing is not None:
        return existing.id

    doc = RawDocument(
        source=source,
        source_url=_pick_text(row, "source_url") or f"udi_promote:{run_id}",
        doc_type="json",
        storage_uri=f"/tmp/{source.lower()}_{run_id}.json",
        sha256=payload_hash,
        run_id=run_id,
        fetched_at=_utcnow(),
        parse_status="PENDING",
        parse_log={"source": source, "source_run_id": source_run_id, "created_at": _utcnow().isoformat()},
        error=None,
    )
    db.add(doc)
    db.flush()
    return doc.id


def _upsert_pending_record(
    db: Session,
    *,
    source_key: str,
    source_run_id: int,
    raw_document_id: UUID,
    reason_code: str,
    row: dict[str, Any],
    registration_no_raw: str | None,
) -> None:
    payload_hash = _payload_hash(dict(row))
    normalized = normalize_registration_no(registration_no_raw) or registration_no_raw
    stmt = insert(PendingRecord).values(
        source_key=source_key,
        source_run_id=source_run_id,
        raw_document_id=raw_document_id,
        payload_hash=payload_hash,
        registration_no_raw=registration_no_raw,
        reason_code=reason_code,
        reason=f"{source_key} promote pending",
        candidate_registry_no=normalized,
        candidate_company=_extract_company(row),
        candidate_product_name=_pick_text(row, "product_name", "cpmctymc", "spmc", "brand"),
        status="open",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[PendingRecord.source_run_id, PendingRecord.payload_hash],
        set_={
            "raw_document_id": stmt.excluded.raw_document_id,
            "registration_no_raw": stmt.excluded.registration_no_raw,
            "reason_code": stmt.excluded.reason_code,
            "reason": stmt.excluded.reason,
            "candidate_registry_no": stmt.excluded.candidate_registry_no,
            "candidate_company": stmt.excluded.candidate_company,
            "candidate_product_name": stmt.excluded.candidate_product_name,
            "status": "open",
            "updated_at": text("NOW()"),
        },
    )
    db.execute(stmt)


def _log_registration_stub_change(
    db: Session,
    *,
    registration_id: UUID,
    before: dict[str, Any],
    after: dict[str, Any],
    source_run_id: int | None,
    source: str,
    raw_document_id: UUID | None,
) -> None:
    if before == after:
        return
    db.add(
        ChangeLog(
            product_id=None,
            entity_type="registration",
            entity_id=registration_id,
            change_type="update",
            changed_fields={k: {"old": before.get(k), "new": after.get(k)} for k in after},
            before_json=before or None,
            after_json=after,
            before_raw=None,
            after_raw={
                "source": source,
                "raw_document_id": str(raw_document_id) if raw_document_id else None,
                "time": _utcnow().isoformat(),
                "source_hint": "UDI",
                "verified_by_nmpa": False,
            },
            source_run_id=source_run_id,
        )
    )


def _ensure_registration_stub_meta(db: Session, *, registration_id: UUID, source_run_id: int | None, source: str, raw_document_id: UUID | None) -> None:
    reg = db.get(Registration, registration_id)
    if reg is None:
        return
    before = dict(reg.raw_json) if isinstance(reg.raw_json, dict) else {}
    reg.raw_json = _merge_stub(reg.raw_json if isinstance(reg.raw_json, dict) else {})
    after = dict(reg.raw_json)
    if before != after:
        _log_registration_stub_change(
            db,
            registration_id=reg.id,
            before=before,
            after=after,
            source_run_id=source_run_id,
            source=source,
            raw_document_id=raw_document_id,
        )


def _ensure_product_stub(
    db: Session,
    *,
    registration_id: UUID,
    reg_no: str,
    di: str,
    row: dict[str, Any],
) -> tuple[Product, bool]:
    product = db.scalar(
        select(Product)
        .where(Product.registration_id == registration_id)
        .order_by(Product.updated_at.desc(), Product.created_at.desc())
        .limit(1)
    )
    if product is None:
        product = db.scalar(select(Product).where(Product.udi_di == di).limit(1))

    created = False
    if product is None:
        product = Product(
            udi_di=di,
            reg_no=reg_no,
            name=_product_stub_name(row),
            class_name=None,
            approved_date=None,
            expiry_date=None,
            model=None,
            specification=None,
            category=None,
            status="UNKNOWN",
            is_ivd=True,
            ivd_category=_product_ivd_category(row),
            ivd_subtypes=None,
            ivd_reason=None,
            ivd_version=1,
            ivd_source="UDI_PROMOTE",
            ivd_confidence=0.40,
            company_id=None,
            registration_id=registration_id,
            raw_json=_merge_stub({}),
            raw={},
        )
        db.add(product)
        db.flush()
        created = True
    else:
        changed = False
        if not product.registration_id:
            product.registration_id = registration_id
            changed = True
        if not product.reg_no:
            product.reg_no = reg_no
            changed = True
        if not product.name:
            product.name = _product_stub_name(row)
            changed = True
        if not product.status:
            product.status = "UNKNOWN"
            changed = True
        if not isinstance(product.raw_json, dict):
            product.raw_json = {}
        before_raw = dict(product.raw_json)
        product.raw_json = _merge_stub(product.raw_json)
        if before_raw != product.raw_json:
            changed = True
        if changed:
            db.add(product)

    if not isinstance(product.raw_json, dict):
        product.raw_json = {}
    before_merge = dict(product.raw_json)
    product.raw_json = _merge_stub(product.raw_json)
    if before_merge != product.raw_json:
        db.add(product)
    return product, created


def _upsert_product_variant(
    db: Session,
    *,
    di: str,
    reg_no: str | None,
    product: Product | None,
    row: dict[str, Any],
) -> bool:
    registry_no_value = reg_no
    product_id_value = product.id if product is not None else None
    product_name_value = _pick_text(row, "product_name", "cpmctymc", "brand", "spmc")
    model_spec_value = _pick_text(row, "model_spec", "ggxh", "model")
    packaging_value = _as_json_text(row.get("packing_json") or row.get("packaging_json"))
    manufacturer_value = _extract_company(row)
    ivd_category_value = _pick_text(row, "product_type", "cplb", "ivd_category", "category_big")

    stmt = insert(ProductVariant).values(
        di=di,
        registry_no=registry_no_value,
        product_id=product_id_value,
        product_name=product_name_value,
        model_spec=model_spec_value,
        packaging=packaging_value,
        manufacturer=manufacturer_value,
        is_ivd=True,
        ivd_category=ivd_category_value,
        ivd_version="UDI_PROMOTE",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductVariant.di],
        set_={
            "registry_no": func.coalesce(stmt.excluded.registry_no, ProductVariant.registry_no),
            "product_id": func.coalesce(stmt.excluded.product_id, ProductVariant.product_id),
            "product_name": func.coalesce(stmt.excluded.product_name, ProductVariant.product_name),
            "model_spec": func.coalesce(stmt.excluded.model_spec, ProductVariant.model_spec),
            "packaging": func.coalesce(stmt.excluded.packaging, ProductVariant.packaging),
            "manufacturer": func.coalesce(stmt.excluded.manufacturer, ProductVariant.manufacturer),
            "is_ivd": func.coalesce(stmt.excluded.is_ivd, ProductVariant.is_ivd),
            "ivd_category": func.coalesce(stmt.excluded.ivd_category, ProductVariant.ivd_category),
            "ivd_version": func.coalesce(stmt.excluded.ivd_version, ProductVariant.ivd_version),
            "updated_at": text("NOW()"),
        },
    )
    db.execute(stmt)
    return True


def _upsert_mapping(
    db: Session,
    *,
    registration_no: str,
    di: str,
    raw_source_record_id: UUID | None,
    source: str,
    confidence: float = 0.95,
) -> None:
    db.execute(
        text("DELETE FROM product_udi_map WHERE di = :di AND registration_no <> :registration_no"),
        {"di": di, "registration_no": registration_no},
    )
    map_stmt = insert(ProductUdiMap).values(
        registration_no=registration_no,
        di=di,
        source=source,
        match_type="direct",
        confidence=float(confidence),
        match_reason="udi_promote_direct",
        reversible=(float(confidence) < 0.60),
        linked_by=source,
        raw_source_record_id=raw_source_record_id,
    )
    map_stmt = map_stmt.on_conflict_do_update(
        index_elements=[ProductUdiMap.registration_no, ProductUdiMap.di],
        set_={
            "source": map_stmt.excluded.source,
            "match_type": map_stmt.excluded.match_type,
            "confidence": map_stmt.excluded.confidence,
            "match_reason": map_stmt.excluded.match_reason,
            "reversible": map_stmt.excluded.reversible,
            "linked_by": map_stmt.excluded.linked_by,
            "raw_source_record_id": map_stmt.excluded.raw_source_record_id,
            "updated_at": text("NOW()"),
        },
    )
    db.execute(map_stmt)


@dataclass
class UdiPromoteReport:
    scanned: int = 0
    with_registration_no: int = 0
    missing_registration_no: int = 0
    promoted: int = 0
    registration_created: int = 0
    registration_updated: int = 0
    product_created: int = 0
    product_updated: int = 0
    variant_upserted: int = 0
    map_upserted: int = 0
    pending_written: int = 0
    skipped_no_di: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] | None = None

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "with_registration_no": self.with_registration_no,
            "missing_registration_no": self.missing_registration_no,
            "promoted": self.promoted,
            "registration_created": self.registration_created,
            "registration_updated": self.registration_updated,
            "product_created": self.product_created,
            "product_updated": self.product_updated,
            "variant_upserted": self.variant_upserted,
            "map_upserted": self.map_upserted,
            "pending_written": self.pending_written,
            "skipped_no_di": self.skipped_no_di,
            "failed": self.failed,
            "errors": self.errors or [],
        }


def promote_udi_from_device_index(
    db: Session,
    *,
    source_run_id: int | None = None,
    raw_document_id: UUID | None = None,
    source: str = "UDI_PROMOTE",
    dry_run: bool,
    limit: int | None = None,
    offset: int | None = None,
) -> UdiPromoteReport:
    report = UdiPromoteReport(errors=[])
    commit_every = 5000
    pending_ops = 0

    sql = "SELECT * FROM udi_device_index"
    cond: list[str] = []
    params: dict[str, Any] = {}
    if source_run_id is not None:
        cond.append("source_run_id = :source_run_id")
        params["source_run_id"] = int(source_run_id)
    if raw_document_id is not None:
        cond.append("raw_document_id = :raw_document_id")
        params["raw_document_id"] = str(raw_document_id)

    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY updated_at DESC NULLS LAST"
    if isinstance(offset, int) and offset > 0:
        sql += " OFFSET :_offset"
        params["_offset"] = int(offset)
    if isinstance(limit, int) and limit > 0:
        sql += " LIMIT :_limit"
        params["_limit"] = int(limit)

    rows = db.execute(text(sql), params).mappings()

    for row_obj in rows:
        row = dict(row_obj)
        report.scanned += 1
        di = _pick_text(row, "di_norm", "di")
        if not di:
            report.skipped_no_di += 1
            continue

        reg_raw = _pick_text(row, "registration_no_norm", "registration_no", "reg_no", "zczbhhzbapzbh")
        reg_no = normalize_registration_no(reg_raw) if reg_raw else None
        run_id = _extract_source_run_id(row, source_run_id)
        rid = _extract_raw_document_id(row, raw_document_id)

        if not reg_no:
            report.missing_registration_no += 1

            if dry_run:
                continue

            if run_id is None:
                report.failed += 1
                report.errors.append({"di": di, "error": "missing source_run_id for pending_records"})
                continue

            if rid is None:
                try:
                    rid = _ensure_raw_document(db=db, row=row, source=source, source_run_id=run_id)
                except Exception as exc:
                    report.failed += 1
                    report.errors.append({"di": di, "error": str(exc)})
                    continue

            try:
                _upsert_pending_record(
                    db,
                    source_key=source,
                    source_run_id=run_id,
                    raw_document_id=rid,
                    reason_code="NO_REG_NO",
                    row=row,
                    registration_no_raw=reg_raw,
                )
                _upsert_product_variant(
                    db,
                    di=di,
                    reg_no=None,
                    product=None,
                    row=row,
                )
                report.pending_written += 1
            except Exception as exc:
                report.failed += 1
                report.errors.append({"di": di, "error": str(exc)})
            finally:
                pending_ops += 1
                if not dry_run and pending_ops >= commit_every:
                    db.commit()
                    pending_ops = 0
            continue

        report.with_registration_no += 1
        if dry_run:
            report.promoted += 1
            continue

        try:
            src_record_id = _as_uuid(_pick_text(row, "raw_source_record_id"))
            if src_record_id is None:
                src_record_id = None

            reg_result = upsert_registration_with_contract(
                db,
                registration_no=reg_no,
                incoming_fields={"status": "UNKNOWN"},
                source=source,
                source_run_id=run_id,
                evidence_grade="C",
                source_priority=1000,
                observed_at=_utcnow(),
                raw_source_record_id=src_record_id,
                raw_payload={
                    "source": source,
                    "di": di,
                    "registration_no_raw": reg_raw,
                    "product_name": _pick_text(row, "product_name", "cpmctymc", "brand", "spmc"),
                    "registration_no_norm": reg_no,
                },
                write_change_log=True,
            )

            reg = db.get(Registration, reg_result.registration_id)
            if reg is None:
                raise RuntimeError("registration not found after upsert")

            _ensure_registration_stub_meta(
                db,
                registration_id=reg.id,
                source_run_id=run_id,
                source=source,
                raw_document_id=rid,
            )
            if reg_result.created:
                report.registration_created += 1
            if reg_result.changed_fields:
                report.registration_updated += 1

            product, product_created = _ensure_product_stub(
                db=db,
                registration_id=reg.id,
                reg_no=reg_no,
                di=di,
                row=row,
            )
            if product_created:
                report.product_created += 1
            else:
                report.product_updated += 1

            db.flush()
            _upsert_product_variant(
                db,
                di=di,
                reg_no=reg_no,
                product=product,
                row=row,
            )
            _upsert_mapping(
                db,
                registration_no=reg.registration_no,
                di=di,
                raw_source_record_id=src_record_id,
                source=source,
                confidence=0.95,
            )
            report.variant_upserted += 1
            report.map_upserted += 1
            report.promoted += 1
        except Exception as exc:
            report.failed += 1
            report.errors.append({"di": di, "error": str(exc)})
        finally:
            pending_ops += 1
            if not dry_run and pending_ops >= commit_every:
                db.commit()
                pending_ops = 0

    if not dry_run:
        db.commit()
    return report
