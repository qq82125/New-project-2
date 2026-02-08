from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ChangeLog, Company, Product
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


def load_staging_records(staging_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
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

    if not existing:
        product = Product(
            name=record.name,
            reg_no=record.reg_no,
            udi_di=record.udi_di,
            status=record.status,
            approved_date=record.approved_date,
            expiry_date=record.expiry_date,
            class_name=record.class_name,
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
    existing.company_id = company.id if company else None
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


def ingest_staging_records(db: Session, records: list[dict[str, Any]], source_run_id: int | None) -> dict[str, int]:
    stats = {'total': len(records), 'success': 0, 'failed': 0, 'added': 0, 'updated': 0, 'removed': 0}

    for raw in records:
        try:
            record = map_raw_record(raw)
            action, _ = upsert_product_record(db, record, source_run_id)
            stats['success'] += 1
            if action == 'added':
                stats['added'] += 1
            elif action == 'updated':
                stats['updated'] += 1
            elif action == 'removed':
                stats['removed'] += 1
        except Exception:
            stats['failed'] += 1

    db.commit()
    return stats
