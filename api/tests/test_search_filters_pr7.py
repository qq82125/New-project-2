from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.main import app
from app.repositories.products import build_search_query


def _compile_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': False})).lower()


def test_search_route_forwards_new_filter_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_search_products(*args, **kwargs):
        captured.update(kwargs)
        return [], 0

    monkeypatch.setattr('app.main.search_products', _fake_search_products)

    client = TestClient(app)
    resp = client.get(
        '/api/search?q=abc&track=reagent&change_type=update&date_range=30d&sort=recency&page=1&page_size=10'
    )
    assert resp.status_code == 200
    assert captured.get('track') == 'reagent'
    assert captured.get('change_type') == 'update'
    assert captured.get('date_range') == '30d'
    assert captured.get('sort') == 'recency'


def test_build_search_query_applies_track_filter() -> None:
    stmt = build_search_query(
        query=None,
        company=None,
        reg_no=None,
        status=None,
        track='reagent',
        change_type=None,
        date_range=None,
        include_unverified=True,
    )
    sql = _compile_sql(stmt)
    assert 'products.ivd_category ilike' in sql
    assert 'products.category ilike' in sql
    assert 'class' in sql and 'ilike' in sql


def test_build_search_query_update_and_cancel_use_change_log_window() -> None:
    update_stmt = build_search_query(
        query=None,
        company=None,
        reg_no=None,
        status=None,
        track=None,
        change_type='update',
        date_range='30d',
        include_unverified=True,
    )
    update_sql = _compile_sql(update_stmt)
    assert 'from change_log' in update_sql
    assert 'change_log.change_date >=' in update_sql
    assert 'change_log.change_type' in update_sql

    cancel_stmt = build_search_query(
        query=None,
        company=None,
        reg_no=None,
        status=None,
        track=None,
        change_type='cancel',
        date_range='30d',
        include_unverified=True,
    )
    cancel_sql = _compile_sql(cancel_stmt)
    assert 'from change_log' in cancel_sql
    assert 'change_log.change_type' in cancel_sql
    assert 'coalesce(products.status' in cancel_sql
