from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def test_product_params_api_success(monkeypatch) -> None:
    product = SimpleNamespace(
        id=uuid.uuid4(),
        name='示例IVD产品',
        udi_di='UDI-1',
        reg_no='REG-1',
    )
    param = SimpleNamespace(
        id=uuid.uuid4(),
        param_code='LOD',
        value_num=0.12,
        value_text=None,
        unit='ng/mL',
        range_low=None,
        range_high=None,
        conditions={'sample_type': 'serum'},
        confidence=0.91,
        evidence_text='检测下限为0.12 ng/mL',
        evidence_page=3,
        extract_version='param_v1',
    )
    doc = SimpleNamespace(source='NMPA_REGISTRY', source_url='https://example.com/doc.pdf')

    monkeypatch.setattr('app.main.get_product', lambda _db, _id: product if _id else None)
    monkeypatch.setattr('app.main.list_product_params', lambda _db, product, limit: [(param, doc)])

    client = TestClient(main.app)
    main.app.dependency_overrides[main.require_pro] = lambda: SimpleNamespace(id=1, role='admin')
    try:
        r = client.get(f'/api/products/{product.id}/params')
        assert r.status_code == 200
        body = r.json()['data']
        assert body['product_id'] == str(product.id)
        assert body['items'][0]['param_code'] == 'LOD'
        assert body['items'][0]['source'] == 'NMPA_REGISTRY'
    finally:
        main.app.dependency_overrides.pop(main.require_pro, None)
