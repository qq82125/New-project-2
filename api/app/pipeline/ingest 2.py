from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import RawDocument


def save_raw_document(
    db: Session,
    *,
    source: str,
    url: str | None,
    content: bytes,
    doc_type: str,
    run_id: str,
) -> UUID:
    cfg = get_settings()
    sha = hashlib.sha256(content).hexdigest()
    suffix = Path(urlparse(url or '').path).suffix or '.bin'
    root = Path(cfg.raw_storage_dir) / source / datetime.now(timezone.utc).strftime('%Y%m%d')
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / f'{sha}{suffix}'
    file_path.write_bytes(content)
    doc = RawDocument(
        source=source,
        source_url=url,
        doc_type=doc_type,
        storage_uri=str(file_path),
        sha256=sha,
        run_id=run_id,
        fetched_at=datetime.now(timezone.utc),
        parse_status='PENDING',
    )
    db.add(doc)
    db.commit()
    if hasattr(db, 'refresh'):
        db.refresh(doc)
    return doc.id


def mark_raw_document_status(
    db: Session,
    *,
    raw_document_id: UUID,
    parse_status: str,
    parse_log: dict | None = None,
    error: str | None = None,
) -> None:
    if not hasattr(db, 'get'):
        return
    doc = db.get(RawDocument, raw_document_id)
    if not doc:
        return
    doc.parse_status = str(parse_status)
    doc.parse_log = dict(parse_log or {})
    doc.error = (str(error)[:2000] if error else None)
    db.add(doc)
    db.commit()
