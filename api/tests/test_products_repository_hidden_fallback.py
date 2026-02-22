from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.repositories.products import get_product


@dataclass
class _P:
    id: object
    is_hidden: bool
    superseded_by: object | None


class _FakeDB:
    def __init__(self, returns):
        self._returns = list(returns)

    def scalar(self, _stmt):
        if not self._returns:
            return None
        return self._returns.pop(0)


def test_get_product_returns_canonical_when_hidden():
    canonical_id = uuid4()
    hidden = _P(id=uuid4(), is_hidden=True, superseded_by=canonical_id)
    canonical = _P(id=canonical_id, is_hidden=False, superseded_by=None)
    db = _FakeDB([hidden, canonical])

    got = get_product(db, str(hidden.id))

    assert got is canonical


def test_get_product_returns_visible_row_directly():
    product = _P(id=uuid4(), is_hidden=False, superseded_by=None)
    db = _FakeDB([product])

    got = get_product(db, str(product.id))

    assert got is product
