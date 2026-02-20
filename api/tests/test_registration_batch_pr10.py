from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


class _FakeExec:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self


class _FakeDb:
    def __init__(self, *, reg, product, reg_change_rows, prod_change_rows, fallback_rows):
        self.reg = reg
        self.product = product
        self.reg_change_rows = reg_change_rows
        self.prod_change_rows = prod_change_rows
        self.fallback_rows = fallback_rows

    def execute(self, stmt):
        sql = str(stmt).lower()
        if 'from registrations' in sql and 'registration_no in' in sql:
            return _FakeExec([self.reg])
        if 'from products' in sql and 'join companies' in sql:
            return _FakeExec([self.product])
        if 'from product_variants' in sql and 'registration_id in' in sql:
            return _FakeExec([(self.reg.id, 2)])
        if 'from product_variants' in sql and 'registration_id is null' in sql:
            return _FakeExec([])
        if 'from change_log' in sql and "change_log.entity_type = :entity_type_1" in sql:
            return _FakeExec(self.reg_change_rows)
        if 'from change_log join products' in sql:
            return _FakeExec(self.prod_change_rows)
        if 'from field_diffs join nmpa_snapshots' in sql:
            return _FakeExec(self.fallback_rows)
        if 'from product_params' in sql and 'product_params.product_id in' in sql:
            return _FakeExec([(self.product.id, 'param_a'), (self.product.id, 'param_b')])
        if 'from product_params' in sql and 'product_params.registry_no in' in sql:
            return _FakeExec([(self.reg.registration_no, 'param_b'), (self.reg.registration_no, 'param_c')])
        return _FakeExec([])


def test_registration_batch_returns_metrics(monkeypatch) -> None:
    monkeypatch.setattr('app.main.normalize_registration_no', lambda x: x.strip())
    reg = SimpleNamespace(
        id=uuid.uuid4(),
        registration_no='REG-001',
        status='ACTIVE',
        expiry_date=date.today() + timedelta(days=400),
    )
    product = SimpleNamespace(
        id=uuid.uuid4(),
        registration_id=reg.id,
        name='Kit A',
        status='ACTIVE',
        expiry_date=date.today() + timedelta(days=300),
        ivd_category='免疫',
        category='',
        updated_at=datetime.utcnow(),
        company_name='Acme',
    )
    fake_db = _FakeDb(
        reg=reg,
        product=product,
        reg_change_rows=[],
        prod_change_rows=[(reg.id, 4)],
        fallback_rows=[(reg.id, 9)],
    )
    app.dependency_overrides[main.get_db] = lambda: fake_db

    client = TestClient(app)
    resp = client.post('/api/registrations/batch', json={'nos': ['REG-001']})
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 0
    assert body['data']['total'] == 1
    item = body['data']['items'][0]
    assert item['registration_no'] == 'REG-001'
    assert item['di_count'] == 2
    assert item['change_count_30d'] == 4
    assert item['params_coverage'] == 3
    assert item['risk_level'] == 'medium'

    app.dependency_overrides.clear()


def test_registration_batch_requires_list() -> None:
    client = TestClient(app)
    resp = client.post('/api/registrations/batch', json={'nos': 'REG-001'})
    assert resp.status_code == 400
