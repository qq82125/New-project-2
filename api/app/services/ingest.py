from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChangeLog, Company, Product, Registration
from app.services.mapping import UnifiedRecord, diff_fields, map_raw_record

TRACKED_FIELDS = ('name', 'model', 'specification', 'category', 'company_id', 'registration_id')


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


def get_or_create_company(db: Session, unified: UnifiedRecord) -> Company | None:
    if not unified.company_name:
        return None
    stmt = select(Company).where(Company.name == unified.company_name)
    company = db.scalar(stmt)
    if company:
        return company
    company = Company(name=unified.company_name, country=unified.company_country, raw_json={})
    db.add(company)
    db.flush()
    return company


def get_or_create_registration(db: Session, unified: UnifiedRecord) -> Registration | None:
    if not unified.registration_no:
        return None
    stmt = select(Registration).where(Registration.registration_no == unified.registration_no)
    reg = db.scalar(stmt)
    if reg:
        if unified.filing_no and not reg.filing_no:
            reg.filing_no = unified.filing_no
        if unified.registration_status:
            reg.status = unified.registration_status
        return reg
    reg = Registration(
        registration_no=unified.registration_no,
        filing_no=unified.filing_no,
        status=unified.registration_status,
        approval_date=unified.approval_date,
        expiry_date=unified.expiry_date,
        raw_json={},
    )
    db.add(reg)
    db.flush()
    return reg


def _product_state(product: Product) -> dict[str, Any]:
    return {
        'name': product.name,
        'model': product.model,
        'specification': product.specification,
        'category': product.category,
        'company_id': str(product.company_id) if product.company_id else None,
        'registration_id': str(product.registration_id) if product.registration_id else None,
        'raw_json': product.raw_json,
    }


def upsert_unified_record(db: Session, unified: UnifiedRecord, source_run_id: int | None) -> tuple[str, Product]:
    company = get_or_create_company(db, unified)
    registration = get_or_create_registration(db, unified)

    stmt = select(Product).where(Product.udi_di == unified.udi_di)
    existing = db.scalar(stmt)

    if not existing:
        product = Product(
            udi_di=unified.udi_di,
            name=unified.product_name,
            model=unified.model,
            specification=unified.specification,
            category=unified.category,
            company_id=company.id if company else None,
            registration_id=registration.id if registration else None,
            raw_json=unified.raw_json,
        )
        db.add(product)
        db.flush()
        db.add(
            ChangeLog(
                entity_type='product',
                entity_id=product.id,
                change_type='INSERT',
                changed_fields={'all': 'created'},
                before_json=None,
                after_json=_product_state(product),
                source_run_id=source_run_id,
            )
        )
        return 'inserted', product

    before = _product_state(existing)
    existing.name = unified.product_name
    existing.model = unified.model
    existing.specification = unified.specification
    existing.category = unified.category
    existing.company_id = company.id if company else None
    existing.registration_id = registration.id if registration else None
    existing.raw_json = unified.raw_json
    after = _product_state(existing)

    changed = diff_fields(before, after, TRACKED_FIELDS + ('raw_json',))
    if changed:
        db.add(
            ChangeLog(
                entity_type='product',
                entity_id=existing.id,
                change_type='UPDATE',
                changed_fields=changed,
                before_json=before,
                after_json=after,
                source_run_id=source_run_id,
            )
        )
        return 'updated', existing
    return 'unchanged', existing


def ingest_staging_records(db: Session, records: list[dict[str, Any]], source_run_id: int | None) -> tuple[int, int, int]:
    success = 0
    failed = 0
    for raw in records:
        try:
            unified = map_raw_record(raw)
            upsert_unified_record(db, unified, source_run_id)
            success += 1
        except Exception:
            failed += 1
    db.commit()
    return len(records), success, failed
