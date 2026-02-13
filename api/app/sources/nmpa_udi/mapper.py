from __future__ import annotations

from typing import Any


def map_to_variant(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'di': str(row.get('udi_di') or row.get('di') or '').strip(),
        'registry_no': str(row.get('reg_no') or row.get('registration_no') or '').strip() or None,
        'product_name': str(row.get('name') or row.get('product_name') or '').strip() or None,
        'model_spec': str(row.get('model') or row.get('specification') or '').strip() or None,
        'packaging': str(row.get('packaging') or '').strip() or None,
        'manufacturer': str(row.get('manufacturer') or row.get('company') or '').strip() or None,
    }
