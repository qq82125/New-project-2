from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

from app.common.errors import IngestErrorCode
from app.models import ChangeLog, Company, ConflictQueue, PendingDocument, PendingRecord, Product, ProductRejected
from app.ivd.classifier import DEFAULT_VERSION as IVD_CLASSIFIER_VERSION, classify
from app.services.mapping import ProductRecord, diff_fields, map_raw_record
from app.services.nmpa_assets import record_shadow_diff_failure, shadow_write_nmpa_snapshot_and_diffs
from app.services.normalize_keys import normalize_registration_no
from app.services.pending_mode import should_enqueue_pending_documents, should_enqueue_pending_records
from app.services.source_contract import apply_field_policy, upsert_registration_with_contract
from app.services.udi_parse import parse_packing_list, parse_storage_list

TRACKED_FIELDS = (
    'status',
    'expiry_date',
    'approved_date',
    'company_id',
    'registration_id',
    'name',
    'reg_no',
    'udi_di',
    'class',
)

_INVALID_NAME_LITERALS = {'na', 'n/a', 'null', 'none', 'unknown', 'test', 'demo', '-', '--', '/', '_'}


def is_valid_product_name(name: str | None) -> bool:
    text = (name or '').strip()
    if not text:
        return False
    if text.lower() in _INVALID_NAME_LITERALS:
        return False
    # reject symbol-only names like "/" "..." "——"
    if not any(ch.isalnum() or ('\u4e00' <= ch <= '\u9fff') for ch in text):
        return False
    return True


def load_staging_records(staging_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def _load_xml_records(file_path: Path) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            # Stream parse large XML files and only keep <device> records.
            for _event, elem in ET.iterparse(file_path, events=('end',)):
                if elem.tag != 'device':
                    continue
                row: dict[str, Any] = {}
                for child in list(elem):
                    # Keep flat scalar fields; selectively retain nested lists we need for UDI contract.
                    if len(child) == 0:
                        row[child.tag] = (child.text or '').strip()
                        continue
                    if child.tag in {"packingList", "storageList"}:
                        items: list[dict[str, Any]] = []
                        for item in list(child):
                            if len(item) == 0:
                                continue
                            d: dict[str, Any] = {}
                            for leaf in list(item):
                                if len(leaf) == 0:
                                    d[leaf.tag] = (leaf.text or "").strip()
                            if d:
                                items.append(d)
                        if items:
                            row[child.tag] = items
                # Canonical structured JSON for contract consumers (deterministic from XML).
                row["packaging_json"] = parse_packing_list(elem)
                row["storage_json"] = parse_storage_list(elem)
                if row:
                    out.append(row)
                elem.clear()
            return out
        except ET.ParseError:
            # Fallback for malformed XML tokens in upstream package.
            text = file_path.read_text(encoding='utf-8', errors='ignore')
            soup = BeautifulSoup(text, 'html.parser')
            for dev in soup.find_all('device'):
                row: dict[str, Any] = {}
                for child in dev.find_all(recursive=False):
                    if child.find(True, recursive=False) is None:
                        row[child.name] = child.get_text(strip=True)
                        continue
                    if child.name in {"packingList", "storageList"}:
                        items: list[dict[str, Any]] = []
                        for item in child.find_all(recursive=False):
                            d: dict[str, Any] = {}
                            for leaf in item.find_all(recursive=False):
                                if leaf.find(True, recursive=False) is not None:
                                    continue
                                d[str(leaf.name)] = leaf.get_text(strip=True)
                            if d:
                                items.append(d)
                        if items:
                            row[child.name] = items
                if row:
                    out.append(row)
        return out

    for file_path in staging_dir.rglob('*'):
        if file_path.suffix.lower() == '.json':
            with file_path.open('r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, list):
                    records.extend([x for x in content if isinstance(x, dict)])
                elif isinstance(content, dict):
                    records.append(content)
        elif file_path.suffix.lower() == '.csv':
            with file_path.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                records.extend([dict(row) for row in reader])
        elif file_path.suffix.lower() == '.xml':
            records.extend(_load_xml_records(file_path))
    return records


def get_or_create_company(db: Session, record: ProductRecord) -> Company | None:
    if not record.company_name:
        return None
    company = db.scalar(select(Company).where(Company.name == record.company_name))
    if company:
        if record.company_country and not company.country:
            company.country = record.company_country
        return company
    company = Company(name=record.company_name, country=record.company_country, raw={}, raw_json={})
    db.add(company)
    db.flush()
    return company


def find_existing_product(
    db: Session,
    record: ProductRecord,
    *,
    registration_id: UUID | None,
) -> Product | None:
    di = str(getattr(record, 'udi_di', '') or '').strip()
    reg = str(getattr(record, 'reg_no', '') or '').strip()

    if registration_id is not None:
        # Registration anchor is canonical; DI is only the variant identifier.
        if di:
            by_di = db.scalar(select(Product).where(Product.udi_di == di))
            if by_di is not None:
                return by_di
        if reg:
            by_anchor = db.scalar(
                select(Product)
                .where(Product.registration_id == registration_id, Product.reg_no == reg)
                .order_by(Product.updated_at.desc())
                .limit(1)
            )
            if by_anchor is not None:
                return by_anchor
        return db.scalar(
            select(Product)
            .where(Product.registration_id == registration_id)
            .order_by(Product.updated_at.desc())
            .limit(1)
        )

    if di:
        # Fallback path for legacy rows without registration anchor.
        return db.scalar(select(Product).where(Product.udi_di == di))

    if reg:
        return db.scalar(select(Product).where(Product.reg_no == reg))
    return None


def _product_state(product: Product) -> dict[str, Any]:
    return {
        'status': product.status,
        'expiry_date': product.expiry_date.isoformat() if product.expiry_date else None,
        'approved_date': product.approved_date.isoformat() if product.approved_date else None,
        'company_id': str(product.company_id) if product.company_id else None,
        'registration_id': str(product.registration_id) if product.registration_id else None,
        'name': product.name,
        'reg_no': product.reg_no,
        'udi_di': product.udi_di,
        'class': product.class_name,
    }


def _detect_change_type(after: Product, changed: dict[str, dict[str, Any]]) -> str:
    if after.status == 'cancelled':
        return 'cancel'
    if after.status == 'expired':
        return 'expire'
    if changed:
        return 'update'
    return 'noop'


def upsert_product_record(
    db: Session,
    record: ProductRecord,
    source_run_id: int | None,
    *,
    source_key: str = 'UNKNOWN',
) -> tuple[str, Product, dict[str, Any] | None, dict[str, Any] | None]:
    registration_id = getattr(record, 'registration_id', None)
    if registration_id is None:
        raise ValueError('registration_id is required for product upsert')

    company = get_or_create_company(db, record)
    existing = find_existing_product(db, record, registration_id=registration_id)
    rec_di = str(getattr(record, 'udi_di', '') or '').strip()
    if (
        existing is not None
        and rec_di
        and str(getattr(existing, 'udi_di', '') or '').strip()
        and str(getattr(existing, 'udi_di', '') or '').strip() != rec_di
    ):
        # Defensive guard: never mutate an existing product into another DI.
        # Different DI should become a separate product row (variant-level distinction).
        existing = None

    ivd_meta = record.raw.get('_ivd') if isinstance(record.raw, dict) else None

    if not existing:
        product = Product(
            name=record.name,
            reg_no=record.reg_no,
            udi_di=record.udi_di,
            status=record.status,
            approved_date=record.approved_date,
            expiry_date=record.expiry_date,
            class_name=record.class_name,
            is_ivd=(bool(ivd_meta.get('is_ivd')) if isinstance(ivd_meta, dict) else None),
            ivd_category=(str(ivd_meta.get('ivd_category')) if isinstance(ivd_meta, dict) and ivd_meta.get('ivd_category') is not None else None),
            ivd_subtypes=(
                [str(x) for x in (ivd_meta.get('ivd_subtypes') or []) if str(x).strip()]
                if isinstance(ivd_meta, dict) and isinstance(ivd_meta.get('ivd_subtypes'), list)
                else None
            ),
            ivd_reason=(ivd_meta.get('reason') if isinstance(ivd_meta, dict) and isinstance(ivd_meta.get('reason'), dict) else None),
            ivd_version=(
                int(ivd_meta.get('rule_version') or ivd_meta.get('version') or 1)
                if isinstance(ivd_meta, dict)
                else 1
            ),
            ivd_source=(str(ivd_meta.get('source')) if isinstance(ivd_meta, dict) and ivd_meta.get('source') is not None else None),
            ivd_confidence=(
                float(ivd_meta.get('confidence'))
                if isinstance(ivd_meta, dict) and ivd_meta.get('confidence') is not None
                else None
            ),
            registration_id=registration_id,
            company_id=company.id if company else None,
            raw=dict(record.raw),
            raw_json=dict(record.raw),
        )
        db.add(product)
        db.flush()

        after_state = _product_state(product)
        db.add(
            ChangeLog(
                product_id=product.id,
                entity_type='product',
                entity_id=product.id,
                change_type='new',
                changed_fields={k: {'old': None, 'new': v} for k, v in after_state.items()},
                before_raw=None,
                after_raw=dict(record.raw),
                before_json=None,
                after_json=after_state,
                source_run_id=source_run_id,
            )
        )
        return 'added', product, None, after_state

    before_state = _product_state(existing)
    existing_raw_json = dict(existing.raw_json) if isinstance(existing.raw_json, dict) else {}
    provenance = (
        dict(existing_raw_json.get('_field_provenance'))
        if isinstance(existing_raw_json.get('_field_provenance'), dict)
        else {}
    )
    queue_reg_no = normalize_registration_no(record.reg_no or existing.reg_no or '')

    def _queue_unresolved(field_name: str, old_value: Any, new_value: Any, decision_meta: dict[str, Any]) -> None:
        if not queue_reg_no:
            return
        candidates = [
            {
                'source_key': str((provenance.get(field_name, {}) or {}).get('source_key') or 'UNKNOWN'),
                'value': (str(old_value) if old_value is not None else None),
                'observed_at': str((provenance.get(field_name, {}) or {}).get('observed_at') or ''),
            },
            {
                'source_key': str(decision_meta.get('source_key') or source_key),
                'value': (str(new_value) if new_value is not None else None),
                'observed_at': str(decision_meta.get('observed_at') or ''),
                'evidence_grade': str(decision_meta.get('evidence_grade') or ''),
                'source_priority': decision_meta.get('source_priority'),
            },
        ]
        open_row = db.scalar(
            select(ConflictQueue).where(
                ConflictQueue.registration_no == queue_reg_no,
                ConflictQueue.field_name == field_name,
                ConflictQueue.status == 'open',
            )
        )
        if open_row is None:
            db.add(
                ConflictQueue(
                    registration_no=queue_reg_no,
                    registration_id=registration_id,
                    field_name=field_name,
                    candidates=candidates,
                    status='open',
                    source_run_id=source_run_id,
                )
            )
            return
        existing_candidates = open_row.candidates if isinstance(open_row.candidates, list) else []
        existing_candidates.extend(candidates)
        open_row.candidates = existing_candidates
        open_row.updated_at = datetime.now(timezone.utc)
        db.add(open_row)

    def _apply(field_name: str, old_value: Any, new_value: Any) -> bool:
        decision = apply_field_policy(
            db,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            source_key=source_key,
            observed_at=datetime.now(timezone.utc),
            existing_meta=(provenance.get(field_name) if isinstance(provenance.get(field_name), dict) else None),
            source_run_id=source_run_id,
            raw_source_record_id=None,
        )
        if decision.action == 'apply':
            provenance[field_name] = decision.incoming_meta
            return True
        if decision.action == 'conflict':
            _queue_unresolved(field_name, old_value, new_value, decision.incoming_meta)
        return False

    if _apply('name', existing.name, record.name):
        existing.name = record.name
    if _apply('reg_no', existing.reg_no, record.reg_no):
        existing.reg_no = record.reg_no
    if _apply('udi_di', existing.udi_di, record.udi_di):
        existing.udi_di = record.udi_di
    if _apply('registration_id', existing.registration_id, registration_id):
        existing.registration_id = registration_id
    if _apply('status', existing.status, record.status):
        existing.status = record.status
    if _apply('approved_date', existing.approved_date, record.approved_date):
        existing.approved_date = record.approved_date
    if _apply('expiry_date', existing.expiry_date, record.expiry_date):
        existing.expiry_date = record.expiry_date
    if _apply('class', existing.class_name, record.class_name):
        existing.class_name = record.class_name
    if isinstance(ivd_meta, dict):
        existing.is_ivd = bool(ivd_meta.get('is_ivd'))
        existing.ivd_category = str(ivd_meta.get('ivd_category')) if ivd_meta.get('ivd_category') is not None else None
        existing.ivd_subtypes = (
            [str(x) for x in (ivd_meta.get('ivd_subtypes') or []) if str(x).strip()]
            if isinstance(ivd_meta.get('ivd_subtypes'), list)
            else None
        )
        existing.ivd_reason = ivd_meta.get('reason') if isinstance(ivd_meta.get('reason'), dict) else None
        existing.ivd_version = int(ivd_meta.get('rule_version') or ivd_meta.get('version') or 1)
        existing.ivd_source = str(ivd_meta.get('source')) if ivd_meta.get('source') is not None else None
        existing.ivd_confidence = float(ivd_meta.get('confidence')) if ivd_meta.get('confidence') is not None else None
    if company:
        # Never wipe an existing company link when incoming row has no company info.
        if _apply('company_id', existing.company_id, company.id):
            existing.company_id = company.id
    existing.raw = dict(record.raw)
    raw_json = dict(record.raw)
    raw_json['_field_provenance'] = provenance
    existing.raw_json = raw_json
    after_state = _product_state(existing)

    changed = diff_fields(before_state, after_state, TRACKED_FIELDS)
    if not changed:
        return 'unchanged', existing, before_state, after_state

    change_type = _detect_change_type(existing, changed)
    db.add(
        ChangeLog(
            product_id=existing.id,
            entity_type='product',
            entity_id=existing.id,
            change_type=change_type,
            changed_fields=changed,
            before_raw=before_state,
            after_raw=dict(record.raw),
            before_json=before_state,
            after_json=after_state,
            source_run_id=source_run_id,
        )
    )

    if change_type in {'cancel', 'expire'}:
        return 'removed', existing, before_state, after_state
    return 'updated', existing, before_state, after_state


def ingest_staging_records(
    db: Session,
    records: list[dict[str, Any]],
    source_run_id: int | None,
    *,
    source: str = 'NMPA_UDI',
    raw_document_id: UUID | None = None,
    reject_audit: bool = True,
) -> dict[str, int]:
    stats = {
        'total': len(records),
        'success': 0,
        'failed': 0,
        'filtered': 0,
        'added': 0,
        'updated': 0,
        'removed': 0,
        # Shadow-write counters (do not block main ingest).
        'diff_failed': 0,
        'diff_written': 0,
    }

    def _extract_classification_code(raw: dict[str, Any], record: ProductRecord) -> str:
        for key in ('classification_code', 'class_code', 'flbm', 'cplb', '类别', '管理类别', 'class', 'class_name'):
            value = raw.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return str(record.class_name or '').strip()

    def _reject_source_key(*, record: ProductRecord, raw: dict[str, Any]) -> str:
        di = str(getattr(record, 'udi_di', '') or '').strip()
        if di:
            return f'di:{di}'
        reg = str(getattr(record, 'reg_no', '') or '').strip()
        if reg:
            return f'reg:{reg}'
        name = str(getattr(record, 'name', '') or '').strip()
        if name:
            return f'name:{name}'
        # Stable fallback: hash of raw record.
        try:
            payload = json.dumps(raw, ensure_ascii=True, sort_keys=True, default=str).encode('utf-8', errors='ignore')
        except Exception:
            payload = repr(raw).encode('utf-8', errors='ignore')
        return f'rawsha:{hashlib.sha256(payload).hexdigest()}'

    def _upsert_rejected(
        *,
        src: str,
        src_key: str,
        reason: dict[str, Any] | None,
        ivd_version: str | None,
        raw_doc_id: UUID | None,
    ) -> None:
        # SQLAlchemy Session: upsert to enforce idempotency.
        if hasattr(db, 'execute'):
            stmt = insert(ProductRejected).values(
                source=src,
                source_key=src_key,
                raw_document_id=raw_doc_id,
                reason=reason,
                ivd_version=ivd_version,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ProductRejected.source, ProductRejected.source_key],
                set_={
                    'raw_document_id': stmt.excluded.raw_document_id,
                    'reason': stmt.excluded.reason,
                    'ivd_version': stmt.excluded.ivd_version,
                    'rejected_at': func.now(),
                },
            )
            db.execute(stmt)
            return

        # Fake/in-memory DB used in unit tests: dedupe by (source, source_key).
        try:
            items = getattr(db, 'items', None)
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, ProductRejected) and getattr(it, 'source', None) == src and getattr(it, 'source_key', None) == src_key:
                        it.raw_document_id = raw_doc_id
                        it.reason = reason
                        it.ivd_version = ivd_version
                        return
        except Exception:
            pass

        db.add(
            ProductRejected(
                source=src,
                source_key=src_key,
                raw_document_id=raw_doc_id,
                reason=reason,
                ivd_version=ivd_version,
            )
        )

    for raw in records:
        try:
            record = map_raw_record(raw)
            if not is_valid_product_name(record.name):
                stats['filtered'] += 1
                continue
            decision = classify(
                {
                    'name': record.name,
                    'classification_code': _extract_classification_code(raw, record),
                },
                version=IVD_CLASSIFIER_VERSION,
            )
            if not bool(decision.get('is_ivd')):
                if reject_audit:
                    src_key = _reject_source_key(record=record, raw=raw)
                    _upsert_rejected(
                        src=str(source or 'unknown'),
                        src_key=src_key,
                        raw_doc_id=raw_document_id,
                        reason={'decision': decision},
                        ivd_version=str(decision.get('version') or IVD_CLASSIFIER_VERSION),
                    )
                stats['filtered'] += 1
                continue

            reg_no_norm = normalize_registration_no(record.reg_no)
            if not reg_no_norm:
                # Canonical key gate: missing registration_no must not write registrations/products.
                # Keep evidence chain via raw_document_id, and enqueue a pending row for ops/manual resolution.
                if raw_document_id and source_run_id is not None:
                    try:
                        payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                    except Exception:
                        payload = repr(raw).encode("utf-8", errors="ignore")
                    payload_hash = hashlib.sha256(payload).hexdigest()
                    try:
                        if should_enqueue_pending_records():
                            stmt = insert(PendingRecord).values(
                                source_key=str(source or "UNKNOWN").strip().upper() or "UNKNOWN",
                                source_run_id=int(source_run_id),
                                raw_document_id=raw_document_id,
                                payload_hash=payload_hash,
                                registration_no_raw=(str(record.reg_no or "").strip() or None),
                                reason_code="NO_REG_NO",
                                candidate_registry_no=(str(record.reg_no or "").strip() or None),
                                candidate_company=str(record.company_name or "").strip() or None,
                                candidate_product_name=str(record.name or "").strip() or None,
                                reason=json.dumps(
                                    {
                                        "error_code": IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                                        "message": "registration_no is required before structured upsert",
                                    },
                                    ensure_ascii=False,
                                ),
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
                                    "updated_at": func.now(),
                                },
                            )
                            db.execute(stmt)

                        if should_enqueue_pending_documents():
                            # Document-level backlog: raw_document missing canonical key
                            doc_stmt = insert(PendingDocument).values(
                                raw_document_id=raw_document_id,
                                source_run_id=int(source_run_id),
                                reason_code="NO_REG_NO",
                                status="pending",
                            )
                            doc_stmt = doc_stmt.on_conflict_do_update(
                                index_elements=[PendingDocument.raw_document_id],
                                set_={
                                    "source_run_id": doc_stmt.excluded.source_run_id,
                                    "reason_code": doc_stmt.excluded.reason_code,
                                    "status": "pending",
                                    "updated_at": func.now(),
                                },
                            )
                            db.execute(doc_stmt)
                    except Exception:
                        # Do not block the main ingest path on pending enqueue failures.
                        db.rollback()
                if reject_audit:
                    src_key = _reject_source_key(record=record, raw=raw)
                    _upsert_rejected(
                        src=str(source or 'unknown'),
                        src_key=src_key,
                        raw_doc_id=raw_document_id,
                        reason={
                            'error_code': IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                            'message': 'registration_no is required before structured upsert',
                        },
                        ivd_version=str(decision.get('version') or IVD_CLASSIFIER_VERSION),
                    )
                stats['filtered'] += 1
                continue

            record.reg_no = reg_no_norm
            reg_upsert = upsert_registration_with_contract(
                db,
                registration_no=reg_no_norm,
                incoming_fields={
                    'approval_date': record.approved_date,
                    'expiry_date': record.expiry_date,
                    'status': record.status,
                },
                source=str(source or 'UNKNOWN'),
                source_run_id=source_run_id,
                evidence_grade='A',
                source_priority=100,
                observed_at=None,
                raw_source_record_id=None,
                raw_payload=raw,
                write_change_log=True,
            )
            record.reg_no = reg_upsert.registration_no
            # Persist explainable IVD classification metadata with each accepted record.
            record.raw['_ivd'] = {
                'is_ivd': True,
                'ivd_category': decision.get('ivd_category'),
                'ivd_subtypes': decision.get('ivd_subtypes') or [],
                'reason': decision.get('reason'),
                # Back-compat: keep numeric `version` for DB mapping (products.ivd_version is INTEGER).
                'version': int(decision.get('rule_version') or 1),
                # Human-readable classifier version string for audit/debug.
                'version_label': decision.get('version', IVD_CLASSIFIER_VERSION),
                'source': decision.get('source') or 'RULE',
                'confidence': decision.get('confidence', 0.5),
            }
            setattr(record, 'registration_id', reg_upsert.registration_id)
            action, product, before_state, after_state = upsert_product_record(
                db,
                record,
                source_run_id,
                source_key=str(source or 'UNKNOWN'),
            )
            stats['success'] += 1
            if action == 'added':
                stats['added'] += 1
            elif action == 'updated':
                stats['updated'] += 1
            elif action == 'removed':
                stats['removed'] += 1

            if str(source or '') == 'NMPA_UDI':
                # Shadow write: NMPA snapshots + field diffs (registration-centric SSOT).
                # Must not change main ingest semantics (IVD-only products) and must not block.
                try:
                    res = shadow_write_nmpa_snapshot_and_diffs(
                        db,
                        record=record,
                        product_before=before_state,
                        product_after=after_state,
                        source_run_id=source_run_id,
                        raw_document_id=raw_document_id,
                    )
                    if not res.ok:
                        stats['diff_failed'] += 1
                        try:
                            record_shadow_diff_failure(
                                db,
                                raw_document_id=raw_document_id,
                                source_run_id=source_run_id,
                                registration_no=getattr(record, "reg_no", None),
                                error=str(res.error or "shadow diff returned ok=false"),
                            )
                        except Exception:
                            pass
                    else:
                        stats['diff_written'] += int(res.diffs_written or 0)
                except Exception as exc:
                    stats['diff_failed'] += 1
                    try:
                        record_shadow_diff_failure(
                            db,
                            raw_document_id=raw_document_id,
                            source_run_id=source_run_id,
                            registration_no=getattr(record, "reg_no", None),
                            error=str(exc),
                        )
                    except Exception:
                        pass
        except Exception:
            # A failed flush leaves the transaction in failed state; rollback and continue.
            db.rollback()
            stats['failed'] += 1

    db.commit()
    return stats
