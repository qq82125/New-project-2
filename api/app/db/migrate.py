from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.db.session import engine


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into executable statements.

    Postgres migrations may contain dollar-quoted blocks (e.g. DO $$ ... $$)
    with internal semicolons. A naive `split(';')` breaks those blocks.
    """

    statements: list[str] = []
    buf: list[str] = []

    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_delim: str | None = None  # e.g. "$$" or "$tag$"

    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ''

        if in_line_comment:
            buf.append(ch)
            if ch == '\n':
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buf.append(ch)
            if ch == '*' and nxt == '/':
                buf.append(nxt)
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue

        if dollar_delim is not None:
            # Look for closing dollar delimiter.
            if sql.startswith(dollar_delim, i):
                buf.append(dollar_delim)
                i += len(dollar_delim)
                dollar_delim = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":  # escaped quote
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        # Not inside any string/comment block.
        if ch == '-' and nxt == '-':
            buf.append(ch)
            buf.append(nxt)
            i += 2
            in_line_comment = True
            continue
        if ch == '/' and nxt == '*':
            buf.append(ch)
            buf.append(nxt)
            i += 2
            in_block_comment = True
            continue
        if ch == "'":
            buf.append(ch)
            in_single = True
            i += 1
            continue
        if ch == '"':
            buf.append(ch)
            in_double = True
            i += 1
            continue
        if ch == '$':
            # Attempt to parse dollar-quote delimiter: $tag$
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            if j < n and sql[j] == '$':
                delim = sql[i : j + 1]
                buf.append(delim)
                i = j + 1
                dollar_delim = delim
                continue

        if ch == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = ''.join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_migration(file_path: Path) -> None:
    sql = file_path.read_text(encoding='utf-8')
    with engine.begin() as conn:
        for stmt in split_sql_statements(sql):
            conn.execute(text(stmt))


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    migration_dir = root / 'migrations'
    for migration_file in sorted(migration_dir.glob('*.sql')):
        run_sql_migration(migration_file)


if __name__ == '__main__':
    main()
