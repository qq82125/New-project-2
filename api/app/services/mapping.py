from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class UnifiedRecord:
    udi_di: str
    product_name: str
    model: str | None
    specification: str | None
    category: str | None
    company_name: str | None
    company_country: str | None
    registration_no: str | None
    filing_no: str | None
    registration_status: str | None
    approval_date: date | None
    expiry_date: date | None
    raw_json: dict[str, Any]


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'udi_di': ('udi_di', 'UDI_DI', 'primary_di', '产品标识DI'),
    'product_name': ('product_name', 'name', '产品名称', '产品名'),
    'model': ('model', '型号'),
    'specification': ('specification', '规格'),
    'category': ('category', '管理类别', 'category_name'),
    'company_name': ('company_name', 'manufacturer', '注册人名称', '生产企业名称'),
    'company_country': ('company_country', 'country', '国家地区'),
    'registration_no': ('registration_no', '注册证编号', 'reg_no'),
    'filing_no': ('filing_no', '备案号'),
    'registration_status': ('registration_status', '状态', 'reg_status'),
}


def _pick(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def map_raw_record(raw: dict[str, Any]) -> UnifiedRecord:
    udi_di = _pick(raw, FIELD_ALIASES['udi_di'])
    product_name = _pick(raw, FIELD_ALIASES['product_name'])
    if not udi_di or not product_name:
        raise ValueError('Missing required fields: udi_di/product_name')

    return UnifiedRecord(
        udi_di=udi_di,
        product_name=product_name,
        model=_pick(raw, FIELD_ALIASES['model']),
        specification=_pick(raw, FIELD_ALIASES['specification']),
        category=_pick(raw, FIELD_ALIASES['category']),
        company_name=_pick(raw, FIELD_ALIASES['company_name']),
        company_country=_pick(raw, FIELD_ALIASES['company_country']),
        registration_no=_pick(raw, FIELD_ALIASES['registration_no']),
        filing_no=_pick(raw, FIELD_ALIASES['filing_no']),
        registration_status=_pick(raw, FIELD_ALIASES['registration_status']),
        approval_date=None,
        expiry_date=None,
        raw_json=raw,
    )


def diff_fields(before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    changed: dict[str, dict[str, Any]] = {}
    for field in fields:
        if before.get(field) != after.get(field):
            changed[field] = {'before': before.get(field), 'after': after.get(field)}
    return changed
