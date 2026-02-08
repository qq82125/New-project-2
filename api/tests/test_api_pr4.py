from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from base64 import b64encode
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


def test_search_api_returns_envelope(monkeypatch) -> None:
    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')
    product = SimpleNamespace(
        id=uuid.uuid4(),
        udi_di='UDI-1',
        reg_no='REG-1',
        name='Test Kit',
        status='active',
        approved_date=None,
        expiry_date=None,
        class_name='II',
        company=company,
    )

    monkeypatch.setattr('app.main.search_products', lambda *args, **kwargs: ([product], 1))

    client = TestClient(app)
    resp = client.get('/api/search?q=test&page=1&page_size=10&sort_by=name&sort_order=asc')
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 0
    assert body['data']['total'] == 1
    assert body['data']['items'][0]['product']['name'] == 'Test Kit'


def test_product_detail_404(monkeypatch) -> None:
    monkeypatch.setattr('app.main.get_product', lambda *args, **kwargs: None)

    client = TestClient(app)
    resp = client.get('/api/products/00000000-0000-0000-0000-000000000000')
    assert resp.status_code == 404


def test_validation_422_on_invalid_page() -> None:
    client = TestClient(app)
    resp = client.get('/api/search?page=0')
    assert resp.status_code == 422


def test_dashboard_summary(monkeypatch) -> None:
    monkeypatch.setattr('app.main.get_summary', lambda *args, **kwargs: (date(2026, 1, 1), date(2026, 1, 31), 3, 2, 1, 10))

    client = TestClient(app)
    resp = client.get('/api/dashboard/summary?days=30')
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 0
    assert body['data']['total_new'] == 3


def test_status_api(monkeypatch) -> None:
    run = SimpleNamespace(
        id=1,
        source='nmpa_udi',
        status='success',
        message=None,
        records_total=10,
        records_success=9,
        records_failed=1,
        added_count=5,
        updated_count=3,
        removed_count=1,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr('app.main.latest_runs', lambda *args, **kwargs: [run])

    client = TestClient(app)
    resp = client.get('/api/status')
    assert resp.status_code == 200
    body = resp.json()
    assert body['data']['latest_runs'][0]['added_count'] == 5


def test_admin_configs_requires_auth(monkeypatch) -> None:
    monkeypatch.setattr('app.main.get_settings', lambda: SimpleNamespace(admin_username='admin', admin_password='secret'))
    client = TestClient(app)
    resp = client.get('/api/admin/configs')
    assert resp.status_code == 401


def test_admin_configs_list_and_update(monkeypatch) -> None:
    settings = SimpleNamespace(admin_username='admin', admin_password='secret')
    monkeypatch.setattr('app.main.get_settings', lambda: settings)

    now = datetime.now(timezone.utc)
    cfg = SimpleNamespace(config_key='field_mapping', config_value={'version': 'v1'}, updated_at=now)
    updated = SimpleNamespace(config_key='field_mapping', config_value={'version': 'v2'}, updated_at=now)

    monkeypatch.setattr('app.main.list_admin_configs', lambda *args, **kwargs: [cfg])
    monkeypatch.setattr('app.main.upsert_admin_config', lambda *args, **kwargs: updated)

    token = b64encode(b'admin:secret').decode('ascii')
    headers = {'Authorization': f'Basic {token}'}

    client = TestClient(app)

    list_resp = client.get('/api/admin/configs', headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()['data']['items'][0]['config_key'] == 'field_mapping'

    put_resp = client.put('/api/admin/configs/field_mapping', json={'config_value': {'version': 'v2'}}, headers=headers)
    assert put_resp.status_code == 200
    assert put_resp.json()['data']['config_value']['version'] == 'v2'
