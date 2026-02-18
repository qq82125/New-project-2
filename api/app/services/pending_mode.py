from __future__ import annotations

from app.core.config import get_settings


def pending_queue_mode() -> str:
    mode = str(get_settings().pending_queue_mode or "").strip().lower()
    if mode in {"both", "document_only", "record_only"}:
        return mode
    return "both"


def should_enqueue_pending_documents() -> bool:
    return pending_queue_mode() in {"both", "document_only"}


def should_enqueue_pending_records() -> bool:
    return pending_queue_mode() in {"both", "record_only"}

