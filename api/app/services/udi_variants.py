from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Product, ProductVariant, Registration
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
