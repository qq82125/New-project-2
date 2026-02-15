from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

from app.models import ChangeLog, Company, Product, ProductRejected
from app.ivd.classifier import DEFAULT_VERSION as IVD_CLASSIFIER_VERSION, classify
from app.services.mapping import ProductRecord, diff_fields, map_raw_record

TRACKED_FIELDS = (
    'status',
    'expiry_date',
    'approved_date',
    'company_id',
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
                    # Keep flat scalar fields only; ignore nested lists/objects such as contactList.
                    if len(child) == 0:
                        row[child.tag] = (child.text or '').strip()
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
                    if child.find(True, recursive=False) is not None:
                        continue
                    row[child.name] = child.get_text(strip=True)
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


def find_existing_product(db: Session, record: ProductRecord) -> Product | None:
    stmt = select(Product).where(or_(Product.udi_di == record.udi_di, Product.reg_no == record.reg_no))
    return db.scalar(stmt)


def _product_state(product: Product) -> dict[str, Any]:
    return {
        'status': product.status,
        'expiry_date': product.expiry_date.isoformat() if product.expiry_date else None,
        'approved_date': product.approved_date.isoformat() if product.approved_date else None,
        'company_id': str(product.company_id) if product.company_id else None,
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


def upsert_product_record(db: Session, record: ProductRecord, source_run_id: int | None) -> tuple[str, Product]:
    company = get_or_create_company(db, record)
    existing = find_existing_product(db, record)

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
        return 'added', product

    before_state = _product_state(existing)
    existing.name = record.name
    existing.reg_no = record.reg_no
    existing.udi_di = record.udi_di
    existing.status = record.status
    existing.approved_date = record.approved_date
    existing.expiry_date = record.expiry_date
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
        existing.company_id = company.id
    existing.raw = dict(record.raw)
    existing.raw_json = dict(record.raw)
    after_state = _product_state(existing)

    changed = diff_fields(before_state, after_state, TRACKED_FIELDS)
    if not changed:
        return 'unchanged', existing

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
        return 'removed', existing
    return 'updated', existing


def ingest_staging_records(
    db: Session,
    records: list[dict[str, Any]],
    source_run_id: int | None,
    *,
    source: str = 'NMPA_UDI',
    raw_document_id: UUID | None = None,
    reject_audit: bool = True,
) -> dict[str, int]:
    stats = {'total': len(records), 'success': 0, 'failed': 0, 'filtered': 0, 'added': 0, 'updated': 0, 'removed': 0}

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
            action, _ = upsert_product_record(db, record, source_run_id)
            stats['success'] += 1
            if action == 'added':
                stats['added'] += 1
            elif action == 'updated':
                stats['updated'] += 1
            elif action == 'removed':
                stats['removed'] += 1
        except Exception:
            # A failed flush leaves the transaction in failed state; rollback and continue.
            db.rollback()
            stats['failed'] += 1

    db.commit()
    return stats
