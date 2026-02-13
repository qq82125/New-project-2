from __future__ import annotations

from pathlib import Path

import time

from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from app.db.session import engine


LOCK_KEY = 947_221_331  # arbitrary constant, stable across containers


def run_sql_migration(file_path: Path) -> None:
    sql = file_path.read_text(encoding='utf-8')
    with engine.begin() as conn:
        for statement in sql.split(';'):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))


def _with_advisory_lock(fn) -> None:
    # Serialize migrations across api/worker containers to avoid deadlocks.
    with engine.begin() as conn:
        conn.execute(text('SELECT pg_advisory_lock(:k)'), {'k': LOCK_KEY})
    try:
        fn()
    finally:
        with engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_unlock(:k)'), {'k': LOCK_KEY})


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    migration_dir = root / 'migrations'

    def _run_all():
        for migration_file in sorted(migration_dir.glob('*.sql')):
            run_sql_migration(migration_file)

    # Retry on Postgres deadlocks (40P01) which can happen on startup races.
    for attempt in range(1, 6):
        try:
            _with_advisory_lock(_run_all)
            return
        except OperationalError as e:
            pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
            if pgcode != '40P01' or attempt >= 5:
                raise
            time.sleep(0.5 * attempt)


if __name__ == '__main__':
    main()
