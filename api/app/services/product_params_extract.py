from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ivd.param_extract import extract_from_text
from app.models import ProductParam, RawDocument
from app.pipeline.doc_reader import iter_text_pages, read_file_bytes
from app.pipeline.normalize import bind_product_for_document, normalize_params_to_db


@dataclass
class ExtractParamsResult:
    raw_document_id: UUID
    dry_run: bool
    di: str | None
    registry_no: str | None
    bound_product_id: str | None
    pages: int
    extracted: int
    deleted_existing: int
    extract_version: str
    parse_log: dict


def extract_params_for_raw_document(
    db: Session,
    *,
    raw_document_id: UUID,
    di: str | None = None,
    registry_no: str | None = None,
    extract_version: str = 'param_v1_20260213',
    dry_run: bool = True,
) -> ExtractParamsResult:
    doc = db.get(RawDocument, raw_document_id)
    if doc is None:
        raise RuntimeError('raw document not found')

    content = read_file_bytes(doc.storage_uri)
    filename = Path(str(doc.storage_uri)).name

    pages = list(iter_text_pages(content=content, doc_type=doc.doc_type, filename=filename))
    if not pages:
        pages = []

    bound = bind_product_for_document(db, di=di, registry_no=registry_no)

    extracted_total = 0
    errors: list[str] = []
    if dry_run:
        for p in pages:
            try:
                extracted_total += len(extract_from_text(p.text))
            except Exception as exc:
                errors.append(str(exc))
        parse_log = {
            'kind': 'product_params_extract',
            'mode': 'dry_run',
            'extract_version': extract_version,
            'pages': len(pages),
            'extracted': extracted_total,
            'di': di,
            'registry_no': registry_no,
            'bound_product_id': (str(bound.id) if bound else None),
            'errors': errors,
            'ran_at': datetime.now(timezone.utc).isoformat(),
        }
        return ExtractParamsResult(
            raw_document_id=raw_document_id,
            dry_run=True,
            di=di,
            registry_no=registry_no,
            bound_product_id=(str(bound.id) if bound else None),
            pages=len(pages),
            extracted=extracted_total,
            deleted_existing=0,
            extract_version=extract_version,
            parse_log=parse_log,
        )

    # Execute mode: replace existing params for this document+version.
    deleted_existing = int(
        db.execute(
            delete(ProductParam).where(
                ProductParam.raw_document_id == raw_document_id,
                ProductParam.extract_version == extract_version,
            )
        ).rowcount
        or 0
    )
    db.commit()

    for p in pages:
        try:
            extracted_total += normalize_params_to_db(
                db,
                raw_document_id=raw_document_id,
                text=p.text,
                di=di,
                registry_no=registry_no,
                extract_version=extract_version,
                evidence_page=p.page,
            )
        except Exception as exc:
            errors.append(str(exc))

    parse_log = {
        'kind': 'product_params_extract',
        'mode': 'execute',
        'extract_version': extract_version,
        'pages': len(pages),
        'deleted_existing': deleted_existing,
        'extracted': extracted_total,
        'di': di,
        'registry_no': registry_no,
        'bound_product_id': (str(bound.id) if bound else None),
        'errors': errors,
        'ran_at': datetime.now(timezone.utc).isoformat(),
    }
    doc.parse_status = 'PARSED'
    doc.parse_log = parse_log
    doc.error = None if not errors else '; '.join(errors)[:5000]
    db.add(doc)
    db.commit()

    return ExtractParamsResult(
        raw_document_id=raw_document_id,
        dry_run=False,
        di=di,
        registry_no=registry_no,
        bound_product_id=(str(bound.id) if bound else None),
        pages=len(pages),
        extracted=extracted_total,
        deleted_existing=deleted_existing,
        extract_version=extract_version,
        parse_log=parse_log,
    )


@dataclass
class RollbackParamsResult:
    raw_document_id: UUID
    dry_run: bool
    deleted: int


def rollback_params_for_raw_document(db: Session, *, raw_document_id: UUID, dry_run: bool = True) -> RollbackParamsResult:
    if dry_run:
        cnt = int(
            db.scalar(select(func.count(ProductParam.id)).where(ProductParam.raw_document_id == raw_document_id))
            or 0
        )
        return RollbackParamsResult(raw_document_id=raw_document_id, dry_run=True, deleted=cnt)

    deleted = int(
        db.execute(delete(ProductParam).where(ProductParam.raw_document_id == raw_document_id)).rowcount or 0
    )
    doc = db.get(RawDocument, raw_document_id)
    if doc is not None:
        doc.parse_status = 'PENDING'
        doc.parse_log = {'kind': 'product_params_rollback', 'deleted': deleted, 'ran_at': datetime.now(timezone.utc).isoformat()}
        db.add(doc)
    db.commit()
    return RollbackParamsResult(raw_document_id=raw_document_id, dry_run=False, deleted=deleted)
