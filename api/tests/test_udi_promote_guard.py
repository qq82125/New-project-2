from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from app.services import udi_promote as mod


class _MappingsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return list(self._rows)


class _ScalarsResult:
    def __init__(self, values):
        self._values = list(values)

    def scalars(self):
        return list(self._values)


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.reg_by_id = {}
        self.commits = 0

    def execute(self, stmt, params=None):
        text = str(stmt)
        if "SELECT * FROM udi_device_index" in text:
            return _MappingsResult(self.rows)
        if "SELECT DISTINCT registration_no FROM product_udi_map WHERE di = :di" in text:
            return _ScalarsResult([])
        return _ScalarsResult([])

    def scalar(self, _query):
        return None

    def get(self, _model, rid):
        return self.reg_by_id.get(str(rid))

    def add(self, _obj):
        return None

    def flush(self):
        return None

    def commit(self):
        self.commits += 1


@dataclass
class _UpsertResult:
    registration_id: object
    registration_no: str
    created: bool
    changed_fields: dict


def test_udi_promote_multi_regno_split(monkeypatch):
    db = _FakeDB(
        rows=[
            {
                "di_norm": "DI001",
                "registration_no_norm": "A,B",
                "source_run_id": 41,
                "raw_document_id": None,
            }
        ]
    )
    seen_regnos = []

    def _fake_upsert(*args, **kwargs):
        reg_no = kwargs["registration_no"]
        rid = uuid4()
        db.reg_by_id[str(rid)] = SimpleNamespace(id=rid, registration_no=reg_no, raw_json={})
        seen_regnos.append(reg_no)
        return _UpsertResult(registration_id=rid, registration_no=reg_no, created=False, changed_fields={})

    monkeypatch.setattr(mod, "extract_registration_no_candidates", lambda _raw: ["REGA", "REGB"])
    monkeypatch.setattr(mod, "upsert_registration_with_contract", _fake_upsert)
    monkeypatch.setattr(mod, "_ensure_registration_stub_meta", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_ensure_product_stub", lambda *a, **k: (SimpleNamespace(id=uuid4()), False, False))
    monkeypatch.setattr(mod, "_upsert_product_variant", lambda *a, **k: True)
    monkeypatch.setattr(mod, "_upsert_mapping", lambda *a, **k: True)

    rep = mod.promote_udi_from_device_index(
        db,
        source_run_id=41,
        dry_run=False,
        limit=100,
        offset=0,
    )

    assert rep.multi_regno_records_count == 1
    assert rep.promoted == 2
    assert rep.map_upserted == 2
    assert rep.variant_upserted == 1
    assert seen_regnos == ["REGA", "REGB"]
    assert all("," not in x for x in seen_regnos)


def test_udi_promote_existing_reg_stub_upgrade_no_duplicate_product(monkeypatch):
    db = _FakeDB(
        rows=[
            {
                "di_norm": "DI002",
                "registration_no_norm": "REGX",
                "source_run_id": 41,
                "raw_document_id": None,
            }
        ]
    )
    product_calls = {"count": 0}

    def _fake_upsert(*args, **kwargs):
        reg_no = kwargs["registration_no"]
        rid = uuid4()
        db.reg_by_id[str(rid)] = SimpleNamespace(id=rid, registration_no=reg_no, raw_json={})
        return _UpsertResult(registration_id=rid, registration_no=reg_no, created=False, changed_fields={"raw": 1})

    def _fake_product_stub(*args, **kwargs):
        product_calls["count"] += 1
        return SimpleNamespace(id=uuid4()), False, True

    monkeypatch.setattr(mod, "extract_registration_no_candidates", lambda _raw: ["REGX"])
    monkeypatch.setattr(mod, "upsert_registration_with_contract", _fake_upsert)
    monkeypatch.setattr(mod, "_ensure_registration_stub_meta", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_ensure_product_stub", _fake_product_stub)
    monkeypatch.setattr(mod, "_upsert_product_variant", lambda *a, **k: True)
    monkeypatch.setattr(mod, "_upsert_mapping", lambda *a, **k: True)

    rep = mod.promote_udi_from_device_index(
        db,
        source_run_id=41,
        dry_run=False,
        limit=100,
        offset=0,
    )

    assert rep.promoted == 1
    assert rep.product_created == 0
    assert rep.product_updated == 1
    assert rep.stub_upgraded_count == 1
    assert product_calls["count"] == 1
