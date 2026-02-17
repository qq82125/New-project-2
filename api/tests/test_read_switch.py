from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


def _set_anchor(monkeypatch, enabled: bool) -> None:
    monkeypatch.setattr(
        'app.main._settings',
        lambda: SimpleNamespace(
            use_registration_anchor=bool(enabled),
            auth_cookie_secure=False,
            auth_cookie_name='ivd_session',
            auth_secret='test-secret',
            auth_session_ttl_hours=1,
        ),
    )


def test_search_count_diff_between_legacy_and_anchor(monkeypatch) -> None:
    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')
    products = [
        SimpleNamespace(
            id=uuid.uuid4(),
            registration_id=None,
            udi_di=f'UDI-{i}',
            reg_no=f'REG-{i}',
            name=f'Test {i}',
            status='ACTIVE',
            approved_date=None,
            expiry_date=None,
            class_name='II',
            ivd_category='reagent',
            company=company,
        )
        for i in range(5)
    ]
    monkeypatch.setattr('app.main.search_products', lambda *args, **kwargs: (products, len(products)))

    client = TestClient(app)
    _set_anchor(monkeypatch, False)
    legacy = client.get('/api/search?q=test&page=1&page_size=20')
    assert legacy.status_code == 200
    legacy_total = int(legacy.json()['data']['total'])

    _set_anchor(monkeypatch, True)
    anchor = client.get('/api/search?q=test&page=1&page_size=20')
    assert anchor.status_code == 200
    anchor_total = int(anchor.json()['data']['total'])

    # Gray release guard: search count should remain stable.
    assert abs(anchor_total - legacy_total) <= 1


def test_product_detail_registration_id_missing_rate_drops_with_anchor(monkeypatch) -> None:
    company = SimpleNamespace(id=uuid.uuid4(), name='Acme', country='CN')

    def _mk_product(pid: uuid.UUID):
        return SimpleNamespace(
            id=pid,
            registration_id=None,
            udi_di='UDI-X',
            reg_no=None,
            name='Anchor Candidate',
            status='ACTIVE',
            approved_date=None,
            expiry_date=None,
            class_name='II',
            ivd_category='reagent',
            company=company,
        )

    monkeypatch.setattr('app.main.get_product', lambda _db, pid: _mk_product(uuid.UUID(str(pid))))
    monkeypatch.setattr(
        'app.main._resolve_registration_anchor_context',
        lambda _db, _p: {
            'registration_id': uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
            'reg_no': '国械注准20260001',
            'status': 'ACTIVE',
            'approved_date': None,
            'expiry_date': None,
            'anchor_summary': {'enabled': True, 'source': 'reg_no_or_variant'},
        },
    )

    ids = [str(uuid.uuid4()) for _ in range(3)]
    client = TestClient(app)

    _set_anchor(monkeypatch, False)
    legacy_missing = 0
    for pid in ids:
        r = client.get(f'/api/products/{pid}')
        assert r.status_code == 200
        if r.json()['data']['registration_id'] is None:
            legacy_missing += 1
    legacy_rate = legacy_missing / len(ids)

    _set_anchor(monkeypatch, True)
    anchor_missing = 0
    for pid in ids:
        r = client.get(f'/api/products/{pid}')
        assert r.status_code == 200
        if r.json()['data']['registration_id'] is None:
            anchor_missing += 1
    anchor_rate = anchor_missing / len(ids)

    # Registration anchor should significantly reduce missing registration_id rate.
    assert anchor_rate <= 0.2
    assert (legacy_rate - anchor_rate) >= 0.5
