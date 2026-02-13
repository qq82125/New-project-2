from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class ProductRecord:
    name: str
    reg_no: str | None
    udi_di: str
    status: str
    approved_date: date | None
    expiry_date: date | None
    company_name: str | None
    company_country: str | None
    class_name: str | None
    raw: dict[str, Any]


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'name': ('name', 'product_name', '产品名称', '产品名', 'cpmctymc', 'spmc'),
    'reg_no': ('reg_no', 'registration_no', '注册证编号', '注册号', 'zczbhhzbapzbh'),
    'udi_di': ('udi_di', 'UDI_DI', 'primary_di', '产品标识DI', 'zxxsdycpbs'),
    'status': ('status', 'registration_status', '状态', 'reg_status', 'versionStauts'),
    'approved_date': ('approved_date', 'approval_date', '批准日期', '批准时间', 'cpbsfbrq'),
    'expiry_date': ('expiry_date', 'expire_date', '有效期至', '失效日期', 'tsrq'),
    'company_name': ('company_name', 'manufacturer', '注册人名称', '生产企业名称', 'ylqxzcrbarmc'),
    'company_country': ('company_country', 'country', '国家地区'),
    'class_name': ('class', 'class_name', '管理类别', '类别', 'flbm', 'cplb'),
}


def _is_placeholder_udi(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower().startswith('ivd-')


def _pick(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    return v[:max_len]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip().replace('/', '-')
    if len(text) >= 10:
        text = text[:10]
    try:
        parsed = date.fromisoformat(text)
        if parsed.year > (date.today().year + 2):
            return None
        return parsed
    except ValueError:
        return None


def normalize_status(raw_status: str | None, expiry_date: date | None) -> str:
    text = (raw_status or '').strip().lower()
    if any(keyword in text for keyword in ('注销', 'cancel', 'cancelled')):
        return 'cancelled'
    if expiry_date and expiry_date < date.today():
        return 'expired'
    if text:
        return text
    return 'active'


def map_raw_record(raw: dict[str, Any]) -> ProductRecord:
    name = _pick(raw, FIELD_ALIASES['name'])
    udi_di = _pick(raw, FIELD_ALIASES['udi_di'])
    reg_no = _pick(raw, FIELD_ALIASES['reg_no'])
    if not name:
        raise ValueError('Missing required field: name')
    if not udi_di and not reg_no:
        raise ValueError('Missing required identifier: udi_di/reg_no')
    if _is_placeholder_udi(udi_di):
        raise ValueError('Invalid placeholder udi_di')

    approved_date = _parse_date(_pick(raw, FIELD_ALIASES['approved_date']))
    expiry_date = _parse_date(_pick(raw, FIELD_ALIASES['expiry_date']))
    status = normalize_status(_pick(raw, FIELD_ALIASES['status']), expiry_date)

    return ProductRecord(
        name=name,
        reg_no=_clip(reg_no, 120),
        udi_di=udi_di or f'reg:{reg_no}',
        status=status,
        approved_date=approved_date,
        expiry_date=expiry_date,
        company_name=_clip(_pick(raw, FIELD_ALIASES['company_name']), 255),
        company_country=_clip(_pick(raw, FIELD_ALIASES['company_country']), 80),
        class_name=_clip(_pick(raw, FIELD_ALIASES['class_name']), 120),
        raw=dict(raw),
    )


def diff_fields(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    changed: dict[str, dict[str, Any]] = {}
    for field in fields:
        if before.get(field) != after.get(field):
            changed[field] = {'old': before.get(field), 'new': after.get(field)}
    return changed
