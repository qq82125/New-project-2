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
