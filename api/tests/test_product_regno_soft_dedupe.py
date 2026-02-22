from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.product_regno_dedupe import dedupe_products_by_reg_no


@dataclass
class _FakeProduct:
    id: object
    reg_no: str
    raw_json: dict
    updated_at: datetime
    is_hidden: bool = False
    superseded_by: object | None = None


class _ExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, dup_rows, by_reg):
        self.dup_rows = dup_rows
        self.by_reg = by_reg

    def execute(self, _stmt):
        return _ExecResult(self.dup_rows)

    def scalars(self, stmt):
        params = stmt.compile().params
        reg_no = params.get("reg_no_1")
        return _ScalarResult(self.by_reg.get(reg_no, []))


def test_dedupe_products_by_regno_dry_run_reports_duplicates():
    now = datetime.now(timezone.utc)
    reg = "粤潮械备20140023"
    p1 = _FakeProduct(
        id=uuid4(),
        reg_no=reg,
        raw_json={"_stub": {"is_stub": True, "verified_by_nmpa": False}},
        updated_at=now,
    )
    p2 = _FakeProduct(
        id=uuid4(),
        reg_no=reg,
        raw_json={"_stub": {"is_stub": False, "verified_by_nmpa": True}},
        updated_at=now - timedelta(hours=2),
    )
    p3 = _FakeProduct(
        id=uuid4(),
        reg_no=reg,
        raw_json={"_stub": {"is_stub": False, "verified_by_nmpa": False}},
        updated_at=now - timedelta(hours=1),
    )
    db = _FakeDB([(reg, 3)], {reg: [p1, p2, p3]})

    report = dedupe_products_by_reg_no(db, dry_run=True)

    assert report.dup_regno_count == 1
    assert report.affected_products_count == 3
    assert report.hidden_count == 2
    assert report.sample[0]["reg_no"] == reg
    # dry-run should not mutate
    assert p1.is_hidden is False
    assert p2.is_hidden is False
    assert p3.is_hidden is False


def test_dedupe_products_by_regno_execute_sets_canonical_mapping():
    now = datetime.now(timezone.utc)
    reg = "粤潮械备20200086"
    canonical = _FakeProduct(
        id=uuid4(),
        reg_no=reg,
        raw_json={"_stub": {"is_stub": False, "verified_by_nmpa": True}},
        updated_at=now - timedelta(days=2),
    )
    duplicate = _FakeProduct(
        id=uuid4(),
        reg_no=reg,
        raw_json={"_stub": {"is_stub": False, "verified_by_nmpa": False}},
        updated_at=now,
    )
    db = _FakeDB([(reg, 2)], {reg: [duplicate, canonical]})

    report = dedupe_products_by_reg_no(db, dry_run=False)

    assert report.canonical_count == 1
    assert canonical.is_hidden is False
    assert canonical.superseded_by is None
    assert duplicate.is_hidden is True
    assert duplicate.superseded_by == canonical.id
