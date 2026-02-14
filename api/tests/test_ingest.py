from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models import ChangeLog, Product
from app.services.ingest import upsert_product_record
from app.services.mapping import map_raw_record


class FakeDB:
    def __init__(self) -> None:
        self.items = []

    def add(self, obj) -> None:
        if getattr(obj, 'id', None) is None and hasattr(obj, '__class__'):
            if obj.__class__.__name__ in {'Product', 'Company'}:
                obj.id = uuid.uuid4()
        self.items.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_first_import_generates_new_change_log(monkeypatch) -> None:
    db = FakeDB()
    raw = {'name': 'A', 'udi_di': 'U1', 'reg_no': 'R1', 'class': 'II'}
    record = map_raw_record(raw)

    monkeypatch.setattr('app.services.ingest.get_or_create_company', lambda _db, _record: None)
    monkeypatch.setattr('app.services.ingest.find_existing_product', lambda _db, _record: None)

    action, _product = upsert_product_record(db, record, source_run_id=1)

    logs = [x for x in db.items if isinstance(x, ChangeLog)]
    assert action == 'added'
    assert logs
    assert logs[-1].change_type == 'new'


def test_second_import_generates_update_change_log(monkeypatch) -> None:
    db = FakeDB()
    existing = Product(
        id=uuid.uuid4(),
        name='A',
        reg_no='R1',
        udi_di='U1',
        status='active',
        approved_date=None,
        expiry_date=None,
        class_name='II',
        company_id=None,
        raw={},
        raw_json={},
    )

    raw = {'name': 'A-NEW', 'udi_di': 'U1', 'reg_no': 'R1', 'class': 'III'}
    record = map_raw_record(raw)

    monkeypatch.setattr('app.services.ingest.get_or_create_company', lambda _db, _record: None)
    monkeypatch.setattr('app.services.ingest.find_existing_product', lambda _db, _record: existing)

    action, _ = upsert_product_record(db, record, source_run_id=2)

    logs = [x for x in db.items if isinstance(x, ChangeLog)]
    assert action == 'updated'
    assert logs[-1].change_type == 'update'
    assert 'name' in logs[-1].changed_fields
    assert logs[-1].changed_fields['name']['old'] == 'A'
    assert logs[-1].changed_fields['name']['new'] == 'A-NEW'


def test_ingest_filters_non_ivd_records(monkeypatch) -> None:
    from app.services.ingest import ingest_staging_records

    db = FakeDB()

    monkeypatch.setattr(
        'app.services.ingest.classify',
        lambda raw, version=None: {
            'is_ivd': bool(raw.get('classification_code') == '22'),
            'ivd_category': 'reagent',
            'ivd_subtypes': [],
            'reason': {'by': 'unit_test', 'needs_review': False},
            'version': 'ivd_v1_20260213',
            'rule_version': 1,
            'source': 'RULE',
            'confidence': 0.9,
        },
    )
    monkeypatch.setattr(
        'app.services.ingest.map_raw_record',
        lambda raw: SimpleNamespace(
            name=raw.get('name') or 'x',
            reg_no=raw.get('reg_no'),
            udi_di=raw.get('udi_di') or 'U1',
            status='active',
            approved_date=None,
            expiry_date=None,
            class_name='22',
            company_name=None,
            company_country=None,
            raw=raw,
        ),
    )
    monkeypatch.setattr('app.services.ingest.upsert_product_record', lambda _db, _record, _run_id: ('added', None))

    stats = ingest_staging_records(
        db,
        [
            {'type': 'non-ivd', 'name': '骨科器械', 'udi_di': 'U-NON', 'classification_code': '07'},
            {'type': 'ivd', 'name': '检测试剂', 'udi_di': 'U-IVD', 'classification_code': '22'},
        ],
        source_run_id=1,
    )
    assert stats['total'] == 2
    assert stats['filtered'] == 1
    assert stats['success'] == 1


def test_ingest_writes_ivd_metadata_into_raw(monkeypatch) -> None:
    from app.services.ingest import ingest_staging_records

    db = FakeDB()

    monkeypatch.setattr(
        'app.services.ingest.classify',
        lambda _raw, version=None: {
            'is_ivd': True,
            'ivd_category': 'reagent',
            'ivd_subtypes': [],
            'reason': {'by': 'class_code', 'rule': 'startswith_22', 'needs_review': False},
            'version': 'ivd_v1_20260213',
            'rule_version': 1,
            'source': 'RULE',
            'confidence': 0.9,
        },
    )
    monkeypatch.setattr(
        'app.services.ingest.map_raw_record',
        lambda raw: SimpleNamespace(
            name=raw.get('name') or 'x',
            reg_no=raw.get('reg_no'),
            udi_di=raw.get('udi_di') or 'U1',
            status='active',
            approved_date=None,
            expiry_date=None,
            class_name='22',
            company_name=None,
            company_country=None,
            raw=dict(raw),
        ),
    )
    captured = {}

    def _upsert(_db, record, _run_id):
        captured['raw'] = record.raw
        return 'added', None

    monkeypatch.setattr('app.services.ingest.upsert_product_record', _upsert)
    stats = ingest_staging_records(db, [{'name': '体外诊断试剂盒', 'udi_di': 'U-IVD'}], source_run_id=1)
    assert stats['success'] == 1
    assert captured['raw']['_ivd']['reason']['by'] == 'class_code'
    assert captured['raw']['_ivd']['reason']['rule'] == 'startswith_22'
    assert captured['raw']['_ivd']['version'] == 1


def test_ingest_filters_invalid_product_name(monkeypatch) -> None:
    from app.services.ingest import ingest_staging_records

    db = FakeDB()
    called = {'upsert': 0}

    monkeypatch.setattr(
        'app.services.ingest.map_raw_record',
        lambda raw: SimpleNamespace(
            name=raw.get('name') or '',
            reg_no=raw.get('reg_no'),
            udi_di=raw.get('udi_di') or 'U1',
            status='active',
            approved_date=None,
            expiry_date=None,
            class_name='22',
            company_name=None,
            company_country=None,
            raw=dict(raw),
        ),
    )
    monkeypatch.setattr(
        'app.services.ingest.classify',
        lambda _raw, version=None: {
            'is_ivd': True,
            'ivd_category': 'reagent',
            'ivd_subtypes': [],
            'reason': {'by': 'unit_test', 'needs_review': False},
            'version': 'ivd_v1_20260213',
            'rule_version': 1,
            'source': 'RULE',
            'confidence': 0.9,
        },
    )

    def _upsert(_db, _record, _run_id):
        called['upsert'] += 1
        return 'added', None

    monkeypatch.setattr('app.services.ingest.upsert_product_record', _upsert)

    stats = ingest_staging_records(
        db,
        [
            {'name': '/', 'udi_di': 'U-BAD'},
            {'name': '核酸检测试剂盒', 'udi_di': 'U-GOOD'},
        ],
        source_run_id=1,
    )
    assert stats['total'] == 2
    assert stats['filtered'] == 1
    assert stats['success'] == 1
    assert called['upsert'] == 1
