from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from app.services import udi_variants as mod


class _MappingsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def fetchall(self):
        return list(self._rows)


class _RowsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


@dataclass
class _FakeVariant:
    di: str
    registry_no: str | None


class _FakeDb:
    def __init__(self, *, index_rows, outlier_regs=None, multi_bind_dis=None, existing_variant_by_di=None):
        self.index_rows = list(index_rows)
        self.outlier_regs = set(outlier_regs or [])
        self.multi_bind_dis = set(multi_bind_dis or [])
        self.existing_variant_by_di = dict(existing_variant_by_di or {})
        self.added = []
        self.commits = 0

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        if "FROM udi_device_index udi" in sql:
            return _MappingsResult(self.index_rows)
        if "HAVING COUNT(1) > :threshold" in sql:
            return _RowsResult([(x,) for x in sorted(self.outlier_regs)])
        if "HAVING COUNT(DISTINCT registration_no_norm) > 1" in sql:
            return _RowsResult([(x,) for x in sorted(self.multi_bind_dis)])
        if "SELECT id, registration_no FROM registrations WHERE registration_no = ANY(:arr)" in sql:
            arr = params.get("arr") or []
            rows = [(uuid4(), rno) for rno in arr]
            return _RowsResult(rows)
        return _RowsResult([])

    def scalars(self, _stmt):
        # Product cache query in service startup.
        return _ScalarsResult([])

    def scalar(self, stmt):
        # existing variant by DI check: params contain di_1.
        try:
            di = stmt.compile().params.get("di_1")
        except Exception:
            di = None
        if di is None:
            return None
        return self.existing_variant_by_di.get(str(di))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def test_udi_variants_dedup_and_safety_skip_counts(monkeypatch):
    monkeypatch.setattr(mod, "map_to_variant", lambda r: {"di": r["di_norm"], "registry_no": r["registration_no_norm"]})

    db = _FakeDb(
        index_rows=[
            {"udi_id": "1", "di_norm": "D1", "registration_no_norm": "R1", "model_spec": None, "sku_code": None, "manufacturer_cn": None, "packing_json": None, "raw_document_id": None},
            {"udi_id": "2", "di_norm": "D1", "registration_no_norm": "R1", "model_spec": None, "sku_code": None, "manufacturer_cn": None, "packing_json": None, "raw_document_id": None},
            {"udi_id": "3", "di_norm": "D2", "registration_no_norm": "OUT_REG", "model_spec": None, "sku_code": None, "manufacturer_cn": None, "packing_json": None, "raw_document_id": None},
            {"udi_id": "4", "di_norm": "D3", "registration_no_norm": "R3", "model_spec": None, "sku_code": None, "manufacturer_cn": None, "packing_json": None, "raw_document_id": None},
        ],
        outlier_regs={"OUT_REG"},
        multi_bind_dis={"D3"},
    )

    rep = mod.upsert_udi_variants_from_device_index(
        db,
        source_run_id=41,
        dry_run=True,
        outlier_threshold=100,
    )

    assert rep.scanned == 3  # D1 duplicate collapsed
    assert rep.duplicate_di_skipped == 1
    assert rep.outlier_regno_skipped == 1
    assert rep.multi_bind_di_skipped == 1
    assert rep.upserted == 1


def test_udi_variants_existing_di_reg_mismatch_records_conflict(monkeypatch):
    monkeypatch.setattr(mod, "map_to_variant", lambda r: {"di": r["di_norm"], "registry_no": r["registration_no_norm"]})

    db = _FakeDb(
        index_rows=[
            {"udi_id": "1", "di_norm": "DI_CONFLICT", "registration_no_norm": "NEW_REG", "model_spec": None, "sku_code": None, "manufacturer_cn": None, "packing_json": None, "raw_document_id": None},
        ],
        existing_variant_by_di={"DI_CONFLICT": _FakeVariant(di="DI_CONFLICT", registry_no="OLD_REG")},
    )

    rep = mod.upsert_udi_variants_from_device_index(
        db,
        source_run_id=41,
        dry_run=False,
        outlier_threshold=100,
    )

    assert rep.multi_bind_di_skipped == 1
    assert rep.conflicts_recorded == 1
    assert rep.upserted == 0
    assert db.commits == 1
