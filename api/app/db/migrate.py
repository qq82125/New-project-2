from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.db.session import engine


def run_sql_migration(file_path: Path) -> None:
    sql = file_path.read_text(encoding='utf-8')
    with engine.begin() as conn:
        for statement in sql.split(';'):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    migration_dir = root / 'migrations'
    for migration_file in sorted(migration_dir.glob('*.sql')):
        run_sql_migration(migration_file)


if __name__ == '__main__':
    main()
