from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChangeLog, Company, Product
from app.services.ingest import ingest_staging_records

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REG_NO_KEYS = ('注册证编号',)
NAME_KEYS = ('产品名称', '产品名称中文')
MODEL_KEYS = ('型号', '型号、规格')
APPROVED_KEYS = ('批准日期',)
EXPIRY_KEYS = ('有效期至',)
CLASSIFICATION_KEYS = ('分类编码', '管理类别', '类别')
COMPANY_KEYS = ('注册人名称',)


@dataclass
class SupplementResult:
    scanned_rows: int
    indexed_rows: int
    matched_products: int
    updated_products: int
    skipped_products: int
    files_read: int
    change_logs_written: int = 0
    ingested_total: int = 0
    ingested_success: int = 0
    ingested_filtered: int = 0
    ingested_failed: int = 0
    ingested_added: int = 0
    ingested_updated: int = 0
    company_backfilled: int = 0


def _normalize_reg_no(v: str | None) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = re.sub(r'\s+', '', s)
    s = s.replace('（', '(').replace('）', ')')
    return s


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    text = str(v).strip().replace('.', '-').replace('/', '-')
    m = re.search(r'(20\d{2}-\d{1,2}-\d{1,2})', text)
    if not m:
        return None
    y, mo, d = m.group(1).split('-')
    try:
        parsed = date(int(y), int(mo), int(d))
        if parsed.year > (date.today().year + 2):
            return None
        return parsed
    except Exception:
        return None


def _clip(v: str | None, max_len: int) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:max_len]


def _column_index(cell_ref: str | None) -> int | None:
    if not cell_ref:
        return None
    letters = []
    for ch in cell_ref:
        if 'A' <= ch <= 'Z':
            letters.append(ch)
        elif 'a' <= ch <= 'z':
            letters.append(ch.upper())
        else:
            break
    if not letters:
        return None
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1


def _read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    result: list[str] = []
    with z.open('xl/sharedStrings.xml') as fp:
        for event, elem in ET.iterparse(fp, events=('end',)):
            if event == 'end' and elem.tag == f'{NS}si':
                result.append(''.join(t.text or '' for t in elem.iter(f'{NS}t')))
                elem.clear()
    return result


def _read_xlsx_rows(xlsx_bytes: bytes) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as z:
        sst = _read_shared_strings(z)
        sheet_path = 'xl/worksheets/sheet1.xml'
        if sheet_path not in z.namelist():
            cands = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet')]
            if not cands:
                return
            sheet_path = cands[0]

        headers: dict[int, str] = {}
        header_done = False
        with z.open(sheet_path) as fp:
            for event, row in ET.iterparse(fp, events=('end',)):
                if event != 'end' or row.tag != f'{NS}row':
                    continue
                values: dict[int, str] = {}
                next_idx = 0
                for c in row.findall(f'{NS}c'):
                    col_idx = _column_index(c.attrib.get('r')) or next_idx
                    next_idx = col_idx + 1

                    text_value = ''
                    t = c.attrib.get('t')
                    if t == 'inlineStr':
                        inline_node = c.find(f'{NS}is')
                        if inline_node is not None:
                            text_value = ''.join(tn.text or '' for tn in inline_node.iter(f'{NS}t'))
                    else:
                        v = c.find(f'{NS}v')
                        raw = (v.text or '') if v is not None else ''
                        if t == 's':
                            try:
                                text_value = sst[int(raw)]
                            except Exception:
                                text_value = raw
                        else:
                            text_value = raw
                    values[col_idx] = text_value

                if not header_done:
                    headers = {idx: (val or '').strip() for idx, val in values.items() if (val or '').strip()}
                    header_done = True
                    row.clear()
                    continue

                if not headers:
                    row.clear()
                    continue

                row_map: dict[str, str] = {}
                for idx, h in headers.items():
                    if not h:
                        continue
                    row_map[h] = (values.get(idx) or '').strip()
                if row_map:
                    yield row_map
                row.clear()


def _iter_excel_files(base_dir: Path) -> Iterable[tuple[str, bytes]]:
    for p in sorted(base_dir.iterdir()):
        if p.name.startswith('.'):
            continue
        if p.suffix.lower() == '.xlsx':
            yield p.name, p.read_bytes()
            continue
        if p.suffix.lower() != '.zip':
            continue
        try:
            with zipfile.ZipFile(p) as z:
                for name in z.namelist():
                    if name.lower().endswith('.xlsx'):
                        yield f'{p.name}:{name}', z.read(name)
        except Exception:
            continue


def run_local_registry_supplement(
    db: Session,
    *,
    folder: str,
    dry_run: bool = True,
    source_run_id: int | None = None,
    ingest_new: bool = False,
    ingest_chunk_size: int = 2000,
) -> SupplementResult:
    base = Path(folder)
    if not base.exists() or not base.is_dir():
        raise RuntimeError(f'folder not found: {folder}')

    products = db.execute(
        select(
            Product.id,
            Product.reg_no,
            Product.name,
            Product.model,
            Product.approved_date,
            Product.expiry_date,
            Product.company_id,
        ).where(Product.is_ivd.is_(True), Product.reg_no.is_not(None))
    ).all()
    target_reg_nos = {
        reg_no
        for reg_no in (_normalize_reg_no(p.reg_no) for p in products)
        if reg_no
    }

    registry: dict[str, dict[str, str]] = {}
    company_by_reg: dict[str, str] = {}
    ingest_rows: dict[str, dict[str, str]] = {}
    ingest_stats = {'total': 0, 'success': 0, 'failed': 0, 'filtered': 0, 'added': 0, 'updated': 0, 'removed': 0}
    scanned_rows = 0
    files_read = 0
    for _name, data in _iter_excel_files(base):
        files_read += 1
        for row in _read_xlsx_rows(data):
            scanned_rows += 1
            reg_no = _normalize_reg_no(next((row.get(k) for k in REG_NO_KEYS if row.get(k)), None))
            if not reg_no:
                continue
            if reg_no in target_reg_nos:
                if reg_no in registry:
                    company_name = _clip(next((row.get(k) for k in COMPANY_KEYS if row.get(k)), '') or '', 255) or ''
                    if company_name and not company_by_reg.get(reg_no):
                        company_by_reg[reg_no] = company_name
                    continue
                registry[reg_no] = {
                    'reg_no': reg_no,
                    'name': _clip(next((row.get(k) for k in NAME_KEYS if row.get(k)), '') or '', 500) or '',
                    'model': _clip(next((row.get(k) for k in MODEL_KEYS if row.get(k)), '') or '', 255) or '',
                    'approved_date': next((row.get(k) for k in APPROVED_KEYS if row.get(k)), '') or '',
                    'expiry_date': next((row.get(k) for k in EXPIRY_KEYS if row.get(k)), '') or '',
                    'company_name': _clip(next((row.get(k) for k in COMPANY_KEYS if row.get(k)), '') or '', 255) or '',
                }
                if registry[reg_no]['company_name']:
                    company_by_reg[reg_no] = registry[reg_no]['company_name']
                continue

            if not ingest_new:
                continue
            candidate = {
                '注册证编号': reg_no,
                '产品名称': _clip(next((row.get(k) for k in NAME_KEYS if row.get(k)), '') or '', 500) or '',
                '型号': _clip(next((row.get(k) for k in MODEL_KEYS if row.get(k)), '') or '', 255) or '',
                '批准日期': next((row.get(k) for k in APPROVED_KEYS if row.get(k)), '') or '',
                '有效期至': next((row.get(k) for k in EXPIRY_KEYS if row.get(k)), '') or '',
                '管理类别': next((row.get(k) for k in CLASSIFICATION_KEYS if row.get(k)), '') or '',
                '注册人名称': _clip(next((row.get(k) for k in COMPANY_KEYS if row.get(k)), '') or '', 255) or '',
            }
            old = ingest_rows.get(reg_no)
            if old is None:
                ingest_rows[reg_no] = candidate
            elif (not old.get('注册人名称')) and candidate.get('注册人名称'):
                ingest_rows[reg_no] = candidate

    matched = 0
    updated = 0
    skipped = 0
    company_backfilled = 0
    update_rows: list[dict[str, object]] = []
    change_rows: list[dict[str, object]] = []
    company_id_cache: dict[str, object] = {}

    existing_company_rows = db.execute(select(Company.id, Company.name)).all()
    for c in existing_company_rows:
        if c.name and c.name.strip():
            company_id_cache[c.name.strip()] = c.id

    def _company_id(name: str | None):
        key = (name or '').strip()
        if not key:
            return None
        cid = company_id_cache.get(key)
        if cid is not None:
            return cid
        c = Company(name=key, raw={}, raw_json={})
        db.add(c)
        db.flush()
        company_id_cache[key] = c.id
        return c.id
    for p in products:
        key = _normalize_reg_no(p.reg_no)
        if not key:
            skipped += 1
            continue
        ext = registry.get(key)
        if not ext:
            skipped += 1
            continue
        matched += 1
        changed = False
        changed_fields: dict[str, dict[str, object | None]] = {}
        new_name = p.name
        new_model = p.model
        new_approved = p.approved_date
        new_expiry = p.expiry_date
        new_company_id = p.company_id

        if (not p.name) and ext.get('name'):
            new_name = _clip(ext['name'], 500) or p.name
            changed = True
            changed_fields['name'] = {'old': p.name, 'new': new_name}
        if (not p.model) and ext.get('model'):
            new_model = _clip(ext['model'], 255) or p.model
            changed = True
            changed_fields['model'] = {'old': p.model, 'new': new_model}
        if p.approved_date is None:
            d = _parse_date(ext.get('approved_date'))
            if d is not None:
                new_approved = d
                changed = True
                changed_fields['approved_date'] = {
                    'old': p.approved_date.isoformat() if p.approved_date else None,
                    'new': d.isoformat(),
                }
        if p.expiry_date is None:
            d = _parse_date(ext.get('expiry_date'))
            if d is not None:
                new_expiry = d
                changed = True
                changed_fields['expiry_date'] = {
                    'old': p.expiry_date.isoformat() if p.expiry_date else None,
                    'new': d.isoformat(),
                }
        if p.company_id is None:
            cid = _company_id(ext.get('company_name'))
            if cid is not None:
                new_company_id = cid
                changed = True
                company_backfilled += 1
                changed_fields['company_id'] = {
                    'old': None,
                    'new': str(cid),
                }
        if changed:
            updated += 1
            if not dry_run:
                update_rows.append(
                    {
                        'id': p.id,
                        'name': new_name,
                        'model': new_model,
                        'approved_date': new_approved,
                        'expiry_date': new_expiry,
                        'company_id': new_company_id,
                    }
                )
                before_state = {
                    'name': p.name,
                    'model': p.model,
                    'approved_date': p.approved_date.isoformat() if p.approved_date else None,
                    'expiry_date': p.expiry_date.isoformat() if p.expiry_date else None,
                    'company_id': str(p.company_id) if p.company_id else None,
                }
                after_state = {
                    'name': new_name,
                    'model': new_model,
                    'approved_date': new_approved.isoformat() if new_approved else None,
                    'expiry_date': new_expiry.isoformat() if new_expiry else None,
                    'company_id': str(new_company_id) if new_company_id else None,
                }
                change_rows.append(
                    {
                        'product_id': p.id,
                        'entity_type': 'product',
                        'entity_id': p.id,
                        'change_type': 'update',
                        'changed_fields': changed_fields,
                        'before_json': before_state,
                        'after_json': after_state,
                        'source_run_id': source_run_id,
                    }
                )

    if not dry_run:
        if update_rows:
            db.bulk_update_mappings(Product, update_rows)
            if change_rows:
                db.bulk_insert_mappings(ChangeLog, change_rows)
            db.commit()
        if ingest_new and ingest_rows:
            rows = list(ingest_rows.values())
            chunk_size = max(100, int(ingest_chunk_size))
            for i in range(0, len(rows), chunk_size):
                batch = rows[i : i + chunk_size]
                batch_stats = ingest_staging_records(db, batch, source_run_id, source='local_registry')
                for k in ingest_stats:
                    ingest_stats[k] += int(batch_stats.get(k, 0) or 0)
    elif ingest_new:
        ingest_stats['total'] = len(ingest_rows)

    return SupplementResult(
        scanned_rows=scanned_rows,
        indexed_rows=len(registry),
        matched_products=matched,
        updated_products=updated,
        skipped_products=skipped,
        files_read=files_read,
        change_logs_written=(0 if dry_run else len(change_rows)),
        ingested_total=int(ingest_stats.get('total', 0) or 0),
        ingested_success=int(ingest_stats.get('success', 0) or 0),
        ingested_filtered=int(ingest_stats.get('filtered', 0) or 0),
        ingested_failed=int(ingest_stats.get('failed', 0) or 0),
        ingested_added=int(ingest_stats.get('added', 0) or 0),
        ingested_updated=int(ingest_stats.get('updated', 0) or 0),
        company_backfilled=company_backfilled,
    )
