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
    db.refresh(doc)
    return doc.id
