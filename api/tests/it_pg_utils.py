from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.migrate import split_sql_statements


def it_db_url() -> str | None:
    return os.environ.get("IT_DATABASE_URL")


def require_it_db_url() -> str:
    url = it_db_url()
    if not url:
        pytest.skip("set IT_DATABASE_URL to run postgres integration tests")
    return url


def apply_sql_migrations(conn) -> None:
    proj_root = Path(__file__).resolve().parents[2]  # .../<repo>
    mig_dir = proj_root / "migrations"
    # Filter out accidental local duplicates like "* 2.sql" (common on macOS Finder copies).
    files = [fp for fp in mig_dir.glob("*.sql") if " 2.sql" not in fp.name and " 2." not in fp.name]
    for fp in sorted(files, key=lambda p: p.name):
        sql = fp.read_text(encoding="utf-8")
        for stmt in split_sql_statements(sql):
            conn.exec_driver_sql(stmt)


def assert_table_exists(conn, name: str) -> None:
    ok = conn.execute(text("SELECT to_regclass(:n)"), {"n": f"public.{name}"}).scalar()
    assert ok is not None, f"missing table: {name}"
