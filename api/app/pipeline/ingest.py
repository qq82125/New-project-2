from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
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
    existing = db.scalar(
        select(RawDocument).where(
            RawDocument.source == source,
            RawDocument.run_id == run_id,
            RawDocument.sha256 == sha,
        )
    )
    if existing is not None:
        return existing.id
    suffix = Path(urlparse(url or '').path).suffix or '.bin'
    root = Path(cfg.raw_storage_dir) / source / datetime.now(timezone.utc).strftime('%Y%m%d')
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / f'{sha}{suffix}'
    if not file_path.exists():
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
    db.refresh(doc)
    return doc.id


def save_raw_document_from_path(
    db: Session,
    *,
    source: str,
    url: str | None,
    file_path: Path,
    doc_type: str,
    run_id: str,
) -> UUID:
    """Persist a downloaded file into raw storage and register it in raw_documents."""
    cfg = get_settings()
    suffix = Path(urlparse(url or '').path).suffix or file_path.suffix or '.bin'

    h = hashlib.sha256()
    with file_path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    sha256_hex = h.hexdigest()

    existing = db.scalar(
        select(RawDocument).where(
            RawDocument.source == source,
            RawDocument.run_id == run_id,
            RawDocument.sha256 == sha256_hex,
        )
    )
    if existing is not None:
        return existing.id

    root = Path(cfg.raw_storage_dir) / source / datetime.now(timezone.utc).strftime('%Y%m%d')
    root.mkdir(parents=True, exist_ok=True)
    dest_path = root / f'{sha256_hex}{suffix}'
    if not dest_path.exists():
        with file_path.open('rb') as src, dest_path.open('wb') as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(chunk)

    doc = RawDocument(
        source=source,
        source_url=url,
        doc_type=doc_type,
        storage_uri=str(dest_path),
        sha256=sha256_hex,
        run_id=run_id,
        fetched_at=datetime.now(timezone.utc),
        parse_status='PENDING',
    )
    db.add(doc)
    db.commit()
    # Fake/in-memory DBs used in tests may not implement refresh(); RawDocument.id is client-generated.
    try:
        db.refresh(doc)  # type: ignore[attr-defined]
    except Exception:
        pass
    return doc.id
