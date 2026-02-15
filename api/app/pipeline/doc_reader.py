from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup


@dataclass
class PageText:
    page: int | None
    text: str


def read_file_bytes(storage_uri: str) -> bytes:
    return Path(str(storage_uri)).read_bytes()


def iter_text_pages(*, content: bytes, doc_type: str | None = None, filename: str | None = None) -> Iterable[PageText]:
    """Extract page-level text with best-effort, staying within project dependencies.

    - For PDF: uses pypdf if installed (lazy import).
    - For HTML: uses BeautifulSoup to extract visible text.
    - Otherwise: decodes as UTF-8 with errors ignored.
    """
    name = (filename or '').lower()
    dtype = (doc_type or '').lower()
    is_pdf = dtype == 'pdf' or name.endswith('.pdf')
    if is_pdf:
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception as exc:  # pragma: no cover
            # Keep error explicit; callers can store it in parse_log.
            raise RuntimeError('pypdf is required to parse PDF documents') from exc

        # PdfReader accepts file-like; use bytes buffer.
        import io

        reader = PdfReader(io.BytesIO(content))
        for i, page in enumerate(reader.pages, start=1):
            try:
                txt = page.extract_text() or ''
            except Exception:
                txt = ''
            if txt.strip():
                yield PageText(page=i, text=txt)
        return

    is_html = dtype == 'html' or name.endswith('.html') or name.endswith('.htm')
    if is_html:
        text = content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(text, 'html.parser')
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        cleaned = soup.get_text(separator='\n')
        lines = [x.strip() for x in cleaned.splitlines() if x.strip()]
        yield PageText(page=None, text='\n'.join(lines))
        return

    text = content.decode('utf-8', errors='ignore')
    yield PageText(page=None, text=text)
